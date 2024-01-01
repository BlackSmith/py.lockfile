import json
import operator
import os.path
import platform
import re
import subprocess
import sys
import urllib.parse
import urllib.error
import urllib.request

import toml
import argparse
import distutils.util

LEGACY_ALIASES = {
    "manylinux1_x86_64": "manylinux_2_5_x86_64",
    "manylinux1_i686": "manylinux_2_5_i686",
    "manylinux2010_x86_64": "manylinux_2_12_x86_64",
    "manylinux2010_i686": "manylinux_2_12_i686",
    "manylinux2014_x86_64": "manylinux_2_17_x86_64",
    "manylinux2014_i686": "manylinux_2_17_i686",
    "manylinux2014_aarch64": "manylinux_2_17_aarch64",
    "manylinux2014_armv7l": "manylinux_2_17_armv7l",
    "manylinux2014_ppc64": "manylinux_2_17_ppc64",
    "manylinux2014_ppc64le": "manylinux_2_17_ppc64le",
    "manylinux2014_s390x": "manylinux_2_17_s390x",
}

# ('glibc', '2.38')
GLIBC = platform.libc_ver()

# 'x86_64'
PLATFORM_TYPE = platform.machine()
# 'linux_x86_64'
PLATFORM = distutils.util.get_platform().replace('.', '_').replace('-', '_')

if hasattr(sys, 'pypy_version_info'):
    PYIMPL = 'pp'  # Pypy
elif sys.platform.startswith('java'):
    PYIMPL = 'jy'  # Jython
elif sys.platform == 'cli':
    PYIMPL = 'ip'  # IronPython
else:
    PYIMPL = 'cp'  # CPython

# (3, 9, 18)
PY_VERSION = (sys.version_info.major, sys.version_info.minor,
              sys.version_info.micro)

MUSL_VERSION = None
if 'linux' in PLATFORM and not GLIBC[0]:
    # Musl
    try:
        output = subprocess.check_output(
            ["ldd", "--version"],
            stderr=subprocess.STDOUT,
            shell=True
        )
    except subprocess.CalledProcessError as ex:
        # Ignore error
        output = ex.output
    for row in output.splitlines():
        match = re.match(rb'Version (\d+)\.(\d+)\..*', row, re.I)
        if match:
            MUSL_VERSION = f'{int(match.group(1))}_{int(match.group(2))}'
            break

DISABLE_COLOR = False


class PackageException(Exception): pass     # noqa


def die(message: str, exitcode: int = 1):
    if not DISABLE_COLOR:
        sys.stderr.write(f'\033[31m\u2718 {message}\033[0m\n')
    else:
        sys.stderr.write(f'\u2718 {message}\n')
    sys.exit(exitcode)


def get_current_platform() -> str:
    global PLATFORM, GLIBC
    if 'linux' not in PLATFORM:
        return PLATFORM
    if not GLIBC or not GLIBC[0]:
        return f'musllinux_{MUSL_VERSION}_{platform.machine()}'
    return (f'manylinux_{GLIBC[1].replace(".", "_")}'
            f'_{platform.machine()}')


class Package:
    OPERATORS = {
        '>': operator.gt,
        '<': operator.lt,
        '>=': operator.ge,
        '<=': operator.le,
        '==': operator.eq,
        '!=': operator.ne
    }

    def __init__(self, name: str, version: str, python_version: str,
                 files: [dict], repository: 'Repository'):
        self.name = name
        self.version = version
        self.python_version = python_version if python_version != '*' else None
        self.is_require_build_package = False
        self.repository = repository
        self.__files = []
        self.logs = []
        self.fatal_error = False
        if files:
            self.set_files(files)
        if not self.check_python_version():
            self.logs.append(
                'The python version is not supported by this package.'
            )

    def print_table_line(self, max_name_size: int = 0,
                         max_version_size: int = 0) -> str:
        color = ''
        reset = ''
        if not DISABLE_COLOR:
            color = '\x1b[1;32m' if not self.logs else '\x1b[1;33m'
            reset = '\033[0m'
        icon = "📦" if self.is_wheel_available else "🏗"
        if self.fatal_error:
            color = '\033[31m' if not DISABLE_COLOR else ''
            icon = '\u2718'
        filename = self.__files[0].get('file', '') if self.__files else ''
        print(f"{color}{icon} "
              f"{self.name.ljust(max_name_size)}\t"
              f"{self.version.ljust(max_version_size)}\t"
              f"{filename}{reset}")
        for it in self.logs:
            print(f"\t{color}{it}{reset}")

    def __get_first(self):
        while self.__files and 'url' not in self.__files[0]:
            self.__files.pop(0)
        if not self.__files:
            return None
        return self.__files[0]

    @property
    def is_wheel_available(self) -> bool:
        return self.file.endswith('.whl')

    @property
    def file(self):
        file = self.__get_first()
        if not file:
            return ''
        return file['file']

    @property
    def file_hash(self) -> str:
        file = self.__get_first()
        if not file:
            return ''
        return file['hash']

    @property
    def url(self) -> str:
        file = self.__get_first()
        if not file:
            return None
        return file['url']

    def check_python_version(self):
        if not self.python_version:
            return True
        ops = '|'.join(self.OPERATORS.keys())
        regx = re.compile(rf'^\s*(?P<op>{ops})\s*(?P<num>[0-9\\.\\*]+)\s*$')
        for cond in self.python_version.split(','):
            reg = regx.match(cond)
            if not reg:
                return False
            op = self.OPERATORS[reg.group('op')]
            nums = reg.group('num').split('.')
            py_version = [*PY_VERSION]
            if nums[-1] == '*':
                nums.pop(-1)
                py_version.pop(-1)
            nums = [int(it) for it in nums]
            if not op(py_version, nums):
                return False
        return True

    def manylinux_tag_is_compatible(self, tag):
        # Normalize and parse the tag
        tag = LEGACY_ALIASES.get(tag, tag)
        m = re.match("manylinux_([0-9]+)_([0-9]+)_(.*)", tag)
        if not m:
            return False
        tag_major_str, tag_minor_str, tag_arch = m.groups()
        tag_major = int(tag_major_str)
        tag_minor = int(tag_minor_str)

        if GLIBC[0] != 'glibc':
            return False
        sys_major, sys_minor = GLIBC[1].split('.')
        sys_major = int(sys_major)
        sys_minor = int(sys_minor)

        if (sys_major, sys_minor) < (tag_major, tag_minor):
            return False

        if PLATFORM_TYPE.lower() != tag_arch:
            return False
        return True

    def set_files(self, files: [dict]):
        py_lang = f'{PYIMPL}{PY_VERSION[0]}{PY_VERSION[1]}'
        source_package = None
        is_binary_package = False
        self.__files = []
        for file in files:
            match = re.match(
                r'^(?P<name>[\w.-]+)-'
                r'(?P<version>\d[^-]+)-'
                r'((?P<build_tag>\d[^-]*)-)?'
                r'(?P<python_tag>[^-]+)-'
                r'(?P<abi_tag>[^-]+)-'
                r'(?P<platform>.+)\.whl$',
                file.get('file'))
            if match:
                parsed = match.groupdict()
                package_tag = parsed['python_tag']
                if package_tag != 'none':
                    if f'py{PY_VERSION[0]}' not in package_tag and \
                            py_lang != package_tag:
                        continue

                package_platform = parsed['platform']
                if package_platform != 'any' and PLATFORM != package_platform:
                    # platform is not equal, manylinux or musllinux
                    is_binary_package = True
                    if 'linux' not in PLATFORM:
                        continue

                    if GLIBC[0] == 'glibc':
                        # manylinux
                        if 'manylinux' not in package_platform:
                            continue

                        if not any([self.manylinux_tag_is_compatible(it)
                                    for it in package_platform.split('.')]):
                            continue
                    elif (f'musllinux_{MUSL_VERSION}'
                          f'_{PLATFORM_TYPE}' != package_platform):
                        # musllinux
                        continue
                self.__files.insert(0, file)
            else:
                if re.match(r'^[\w.-]+-[\d.]+\.tar\.gz',
                            file.get('file')):
                    source_package = file

        if source_package:
            self.__files.append(source_package)
            self.is_require_build_package = \
                len(self.__files) == 1 and is_binary_package

    def load_metadata(self, ignore_hash: bool = False,
                      no_binary: bool = False) -> dict:
        """
        Load metadata and verify package
        """
        metadata = self.repository.get_metadata(self.name, self.version)
        for url in metadata.get('urls'):
            if no_binary and url['filename'].endswith('.whl'):
                continue
            for file in self.__files:
                if file['file'] == url['filename']:
                    hash_type, _hash = file['hash'].split(':')
                    if url['digests'][hash_type] == _hash:
                        file['url'] = url['url']
                    else:
                        e_msg = (f'Unmatch package "{file["file"]}" hash '
                                 f' {file["hash"]} != {hash_type}:'
                                 f'{url["digests"][hash_type]}.')
                        if not ignore_hash:
                            raise PackageException(e_msg)
                        self.logs.append(e_msg)
                    break
        if not self.is_wheel_available and self.is_require_build_package:
            self.logs.append('This package will require a build.')

    def download_package(self, target: str) -> None:
        file = self.__get_first()
        if file is None:
            raise PackageException(
                f'The source lock file does not contain a correct reference '
                f'for package {self.name} with required python version and '
                f'CPU architecture.')
        try:
            response = self.repository.get_url_response(file['url'])
            with open(f'{target}/{file["file"]}', 'wb') as fd:
                fd.write(response.read())
        except urllib.error.HTTPError as e:
            raise PackageException(f'Can not download package {file["url"]}:'
                                   f' {e}')


class Repository:

    INSTANCES = {}
    DEFAULT_REPOSITORY = 'pypi.org'

    @classmethod
    def get(cls, name: str) -> 'Repository':
        return Repository.INSTANCES.get(name)

    @classmethod
    def create(cls, name: str, username: str = None, password: str = None):
        repo = Repository(name, username, password)
        cls.INSTANCES[name] = repo
        return repo

    def __init__(self, name: str, username: str = None, password: str = None):
        self.name = name
        self.username = username
        self.password = password
        self.url = 'https://pypi.org'
        self.legacy = False

    def get_url_response(self, url: str):
        username = os.getenv(f'{self.name.upper()}_USERNAME') or self.username
        password = os.getenv(f'{self.name.upper()}_PASSWORD') or self.password
        if username:
            password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, url, username, password)
            auth_handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
            opener = urllib.request.build_opener(auth_handler)
            return opener.open(url)
        else:
            return urllib.request.urlopen(url)

    def __legacy_parse(self, html: str):
        match = re.findall(
            r'<a\s+'
            r'href="(?P<url>[^#"]+)#(?P<hash>[^"]+)"[^>]*>'
            r'(?P<name>[^<]+)'
            r'</a>',
            html)
        res = []
        for it in match:
            hash_type, hash = it[1].split('=', 1)
            res.append({
                'filename': it[2],
                'digests': {hash_type: hash},
                'url': it[0]
            })
        return {'urls': res}

    def get_metadata(self, name: str, version: str) -> dict:
        try:
            if self.legacy:
                response = self.get_url_response(f'{self.url}/{name}')
                return self.__legacy_parse(response.read().decode('utf-8'))
            else:
                response = self.get_url_response(
                    f'{self.url}/pypi/{name}/{version}/json'
                )
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            raise PackageException(
                f'Can not download metadata for package {name}: {e}'
            )


class SourceFile:

    SOURCE_FILES = []
    CREDENTIALS = {}

    def __init__(self, lockfile_path: str):
        self.lockfile_path = lockfile_path

    def __init_subclass__(cls, **kwargs):
        if getattr(cls, 'PRIORITY', 0) == 0:
            SourceFile.SOURCE_FILES.insert(0, cls)
        else:
            SourceFile.SOURCE_FILES.append(cls)

    @classmethod
    def get_parser(cls, file: str = None):
        if file:
            if not os.path.exists(file):
                die(f'The source file  "{file}" does not exist.')
            for source_class in cls.SOURCE_FILES:
                if file.endswith(source_class.FILENAME):
                    return source_class(file)
            die(f'The source file {file} is not supported.')
        else:
            for file in os.listdir(os.getcwd()):
                for source_class in cls.SOURCE_FILES:
                    if file.endswith(source_class.FILENAME):
                        return source_class(file)
            die('The script does not find any supported source files.')

    def load_credentials(self):
        raise NotImplementedError()

    def get_packages(self, package_groups: [str]) -> [Package]:
        raise NotImplementedError()

    def download_packages(self, **kwargs) -> None:
        packages = self.get_packages(kwargs['groups'])
        if not kwargs['dryrun']:
            os.makedirs(kwargs['target'], exist_ok=True)

        max_size_name = max([len(pac.name) for pac in packages])
        max_size_version = max([len(pac.version) for pac in packages])
        for pac in packages:
            try:
                pac.load_metadata(
                    ignore_hash=kwargs['ignore_hash'],
                    no_binary=kwargs['no_binary']
                )
                if not kwargs['dryrun']:
                    pac.download_package(kwargs['target'])
                pac.print_table_line(max_size_name, max_size_version)
            except PackageException as ex:
                if not kwargs['ignore_missing']:
                    die(str(ex))
                pac.logs.append(str(ex))
                pac.fatal_error = True
                pac.print_table_line(max_size_name, max_size_version)


class PoetryLockfile(SourceFile):

    FILENAME = 'poetry.lock'
    DEFAULT_GROUP = 'main'

    def load_credentials(self):
        if 'linux' in PLATFORM:
            home_directory = os.path.expanduser("~")
            poetry_auth = f'{home_directory}/.config/pypoetry/auth.toml'
        elif 'macosx' in PLATFORM:
            home_directory = os.path.expanduser("~")
            poetry_auth = (f'{home_directory}/Library/Application '
                           f'Support/pypoetry/auth.toml')
        else:
            home_directory = os.environ.get('USERPROFILE', '')
            poetry_auth = (f'{home_directory}\\AppData\\Local'
                           f'\\pypoetry\\auth.toml')
        if not os.path.exists(poetry_auth):
            return
        with open(poetry_auth) as fd:
            poetry = toml.load(fd)
            for name, cred in poetry.get('http-basic', {}).items():
                Repository.create(name, cred['username'], cred['password'])

    def get_packages(self, package_groups: [str]) -> [Package]:
        groups = [self.DEFAULT_GROUP] + package_groups
        packages = []
        with open(self.lockfile_path, 'r') as fd:
            data = toml.load(fd)
        for record in data.get('package', []):
            if record.get('category', self.DEFAULT_GROUP) not in groups:
                continue
            name = record['name']
            files = record.get(
                'files',
                data.get('metadata', {}).get('files', {}).get(name, [])
            )
            repo = None
            if 'source' in record:
                repo = Repository.get(record['source']['reference'])
                match = re.match(
                    r'(?P<schema>https?:\/\/)((?P<username>[^:]+):'
                    r'(?P<password>[^@]+)@)?(?P<url>.*)',
                    record['source']['url'],
                    re.I)
                if not repo:
                    repo = Repository.create(
                        record['source']['reference'],
                        match.group('username'),
                        match.group('password')
                    )
                repo.url = f'{match.group("schema")}{match.group("url")}'
                repo.legacy = record['source'].get('type', '') == 'legacy'
            if not repo:
                repo = Repository.get(Repository.DEFAULT_REPOSITORY)
            if not repo:
                die(f'Could not find repository for package {name}.')
            package = Package(name, record['version'],
                              record.get('python-versions'),
                              files, repo)
            packages.append(package)
        return packages


class PdmLockfile(SourceFile):
    FILENAME = 'pdm.lock'
    DEFAULT_GROUP = 'default'

    def load_credentials(self):
        pass

    def get_packages(self, package_groups: [str]) -> [Package]:
        groups = [self.DEFAULT_GROUP] + package_groups
        packages = []
        with open(self.lockfile_path, 'r') as fd:
            data = toml.load(fd)
        for record in data.get('package', []):
            if record.get('category', self.DEFAULT_GROUP) not in groups:
                continue
            name = record['name']
            files = record.get('files', [])
            repo = None
            if 'source' in record:
                repo = Repository.get(record['source']['reference'])
                match = re.match(
                    r'(?P<schema>https?:\/\/)((?P<username>[^:]+):'
                    r'(?P<password>[^@]+)@)?(?P<url>.*)',
                    record['source']['url'],
                    re.I)
                if not repo:
                    repo = Repository.create(
                        record['source']['reference'],
                        match.group('username'),
                        match.group('password')
                    )
                repo.url = f'{match.group("schema")}{match.group("url")}'
                repo.legacy = record['source'].get('type', '') == 'legacy'
            if not repo:
                repo = Repository.get(Repository.DEFAULT_REPOSITORY)
            if not repo:
                die(f'Could not find repository for package {name}.')
            package = Package(name, record['version'],
                              record.get('python-versions'),
                              files, repo)
            packages.append(package)
        return packages


def main(args):
    global PY_VERSION, PLATFORM_TYPE, PLATFORM, GLIBC, MUSL_VERSION, \
        DISABLE_COLOR
    parser = argparse.ArgumentParser(
        description="""
Python package downloader.
---------------------------------

This is a simple tool for download python packages managed by lock file.
Repository credentials can be set by environment variables.

Supported:
    * poetry.lock - Poetry, the repository credentials are automatically loaded
                    from ~/.config/pypoetry/auth.toml.

""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
SOURCEFILE:
    Automatically try to find supported files in current folder.

PLATFORM:
    Your current platform is '{get_current_platform()}'
    See more https://peps.python.org/pep-0491/#file-name-convention
    e.g.:
        * macosx_10_9_x86_64
        * win_amd64
        * manylinux_2_17_x86_64    # glib linux systems (RHEL based system) \
https://peps.python.org/pep-0600/
        * musllinux_1_1_x86_64     # musl linux systems (AlpineLinux) \
https://peps.python.org/pep-0656/

PYTHON_IMPLEMENTATION:
   * 'cp' - CPython
   * 'pp' - Pypy
   * 'ip' - IronPython
   * 'jy' - Jython
"""
    )

    parser.add_argument('-s', '--sourcefile', type=str,
                        help='source file (e.g. poetry.lock)')

    parser.add_argument('-t', '--target',
                        default='./wheels',
                        type=str,
                        help='Download folder (default: %(default)s)')

    parser.add_argument('-g', '--group', action='append', type=str,
                        help='Append optional group of packages (e.g. dev)'
                        )

    parser.add_argument('-p', '--python-version',
                        default='.'.join(str(it) for it in PY_VERSION),
                        action="store",
                        type=str,
                        help='Download packages for python version '
                             '(default: %(default)s).'
                        )

    parser.add_argument('--platform',
                        default=get_current_platform(),
                        action="store",
                        type=str,
                        help='Download packages for platform '
                             '(default: %(default)s).'
                        )

    parser.add_argument('--python-implementation',
                        default=PYIMPL,
                        action="store",
                        choices=['cp', 'ip', 'pp', 'jy'],
                        help='Download packages for python implementation '
                             '(default: %(default)s).'
                        )

    parser.add_argument('--ignore-missing', action="store_true",
                        help='Skip missing packages.')

    parser.add_argument('--ignore-hash', action="store_true",
                        help='Ignore package hash checking.')

    parser.add_argument('--no-binary', action="store_true",
                        help='Download only source packages.')

    parser.add_argument('--dryrun', action="store_true",
                        help='Dry run. No download will be performed.')

    parser.add_argument('--no-color', action="store_true",
                        help='Disable color output.')

    args = parser.parse_args(args)
    if args.no_color:
        DISABLE_COLOR = True

    if args.python_version:
        if not re.match(r"^([0-9]+\.[0-9]+(\.[0-9]+)?)$", args.python_version):
            raise argparse.ArgumentTypeError("Unknown python version.")
        PY_VERSION = [int(it) for it in args.python_version.split('.')]

    if args.platform:
        parsed = args.platform.split('_')
        if parsed[-1] == '64':
            PLATFORM_TYPE = f'{parsed[-2]}_{parsed[-1]}'
        else:
            PLATFORM_TYPE = parsed[-1]
        if 'manylinux' == parsed[0]:
            PLATFORM = f'linux_{PLATFORM_TYPE}'
            GLIBC = ('glibc', f'{parsed[1]}.{parsed[2]}')
        elif 'musllinux' == parsed[0]:
            PLATFORM = f'linux_{PLATFORM_TYPE}'
            GLIBC = ('', '')
            MUSL_VERSION = f'{parsed[1]}_{parsed[2]}'
        else:
            PLATFORM = args.platform

    # Create default repository
    Repository.create(Repository.DEFAULT_REPOSITORY)
    try:
        file_parser: SourceFile = SourceFile.get_parser(args.sourcefile)
        file_parser.load_credentials()
        file_parser.download_packages(**{
            'target': args.target or f'{os.getcwd()}/wheels',
            'groups': args.group or [],
            'dryrun': args.dryrun,
            'ignore_missing': args.ignore_missing,
            'ignore_hash': args.ignore_hash,
            'no_binary': args.no_binary
        })
    except KeyboardInterrupt:
        die("Interrupted by user", exitcode=1)


if __name__ == "__main__":
    main(sys.argv[1:])