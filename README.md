# py.Lockfile

**py.Lockfile** is a tool for downloading of python packages for various OS, CPU
and python versions.

## Motivation
Python projects managed by [poetry](https://python-poetry.org/) have got dependencies saved in `poetry.lock`
file. However, poetry is huge with many dependencies, and it is not necessary for finally deploying your project.
This tool takes `poetry.lock` file and downloads them for target OS, CPU and python version. After that we can install them by `pip`.


## Simple example of usage
```shell
> py.lockfile -s tests/poetry.lock -t wheels/
📦 cffi 1.15.1  cffi-1.15.1-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

> ls wheels/
cffi-1.15.1-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
```

## Advanced options

```shell
> py.lockfile --help
usage: py_lockfile.py [-h] [-s SOURCEFILE] [-t TARGET] [-g GROUP] [-p PYTHON_VERSION] [--platform PLATFORM] [--python-implementation {cp,ip,pp,jy}] [--ignore-missing] [--ignore-hash] [--no-binary] [--dryrun] [--no-color]

Python package downloader.
---------------------------------

optional arguments:
  -h, --help            show this help message and exit
  -s SOURCEFILE, --sourcefile SOURCEFILE
                        source file (e.g. poetry.lock)
  -t TARGET, --target TARGET
                        Download folder (default: ./wheels)
  -g GROUP, --group GROUP
                        Append optional group of packages (e.g. dev)
  -p PYTHON_VERSION, --python-version PYTHON_VERSION
                        Download packages for python version (default: 3.9.18).
  --platform PLATFORM   Download packages for platform (default: manylinux_2_38_x86_64).
  --python-implementation {cp,ip,pp,jy}
                        Download packages for python implementation (default: cp).
  --ignore-missing      Skip missing packages.
  --ignore-hash         Ignore package hash checking.
  --no-binary           Download only source packages.
  --dryrun              Dry run. No download will be performed.
  --no-color            Disable color output.

SOURCEFILE:
    Automatically try to find supported files in current folder.

PLATFORM:
    Your current platform is 'manylinux_2_38_x86_64'
    See more https://peps.python.org/pep-0491/#file-name-convention
    e.g.:
        * macosx_10_9_x86_64
        * win_amd64
        * manylinux_2_17_x86_64    # glib linux systems (RHEL based system) https://peps.python.org/pep-0600/
        * musllinux_1_1_x86_64     # musl linux systems (AlpineLinux) https://peps.python.org/pep-0656/

PYTHON_IMPLEMENTATION:
   * 'cp' - CPython
   * 'pp' - Pypy
   * 'ip' - IronPython
   * 'jy' - Jython
```

Default values of `--python-version`, `--platform` and `--python-implementation` are your current python configuration.
However, you can download packages for different configuration as well. 

```shell
> py.lockfile.py -s tests/poetry.lock -t wheels/ --python-version 2.7 --platform win_amd64
📦 cffi 1.15.1  cffi-1.15.1-cp27-cp27m-win_amd64.whl
```

## Download packages from a private repository
Credentials are automatically loaded from `pypoetry/auth.toml` or we can overwrite them by environment variables.
```shell
<REPO_NAME>_USERNAME=user <REPO_NAME>_PASSWORD=password py.lockfile ...
```

