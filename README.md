[![PyPI](https://img.shields.io/pypi/v/py.lockfile2?color=green&style=plastic)](https://pypi.org/project/py.lockfile2/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/py.lockfile2?style=plastic)
![License](https://img.shields.io/github/license/Blacksmith/py.lockfile?style=plastic)
# py.lockfile

Install
```shell
pip install py.lockfile2
```

**py.lockfile** is a tool for downloading of python packages for various OS, CPU
and python versions.

## Motivation
Python projects managed by [pipenv](https://pipenv.pypa.io/), [poetry](https://python-poetry.org/) or [pdm](https://pdm-project.org/) use 
lock files for freeze packages in specific version.
It is very useful for stability of whole project. However, for installing these
freeze packages, we have to use mentioned package managers, which bring many
unwanted dependencies. It is uncomfortable especially for building of docker
containers.

This tool takes `Pipfile.lock`/`poetry.lock`/`pdm.lock` file and downloads all required packages
(for specific OS, CPU and python version) to target directory. 
After that we can install them by simple `pip`.


## The simple example of usage
```shell
> py.lockfile -s tests/poetry.lock -t wheels/
📦 cffi 1.15.1  cffi-1.15.1-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl

> pip install wheels/*
cffi-1.15.1-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
```

## Advance options

The tool accepts many arguments, the most useable are  `--python-version` and `--platform`.
They can help us to download packages for different python version or OS platform.
Get the correct value of `--platform` attribute for your system, can be
complicated. This command can help `py_lockfile --help | grep 'Your current platform'`

```shell
> py.lockfile --help
usage: py_lockfile [-h] [-s SOURCEFILE] [-t TARGET] [-g GROUP] [-p PYTHON_VERSION] [--platform PLATFORM] [--python-implementation {cp,ip,pp,jy}] [--ignore-missing] [--ignore-hash] [--no-binary] [--dryrun] [--no-color]

Python package downloader.
---------------------------------

This is a simple tool for download python packages managed by lock file.
Repository credentials can be set by environment variables
(PYLF_<NAME>_USERNAME, PYLF_<NAME>_PASSWORD and PYLF_<NAME>_URL).

Supported:
    * Pipfile.lock - Pipenv.
    * poetry.lock - Poetry, the repository credentials are automatically loaded
                    from ~/.config/pypoetry/auth.toml.
    * pdm.lock - PDM, the repository credentials are automatically loaded from
                 pyproject.toml

optional arguments:
  -h, --help            show this help message and exit
  -s SOURCEFILE, --sourcefile SOURCEFILE
                        source file (e.g. Pipfile.lock, poetry.lock or pdm.lock)
  -t TARGET, --target TARGET
                        Download folder (default: ./wheels)
  -g GROUP, --group GROUP
                        Append optional group of packages (e.g. dev)
  -p PYTHON_VERSION, --python-version PYTHON_VERSION
                        Download packages for python version (default: 3.9.5).
  --platform PLATFORM   Download packages for platform (default: manylinux_2_28_x86_64).
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
    Your current platform is 'manylinux_2_28_x86_64'
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

As default values of `--python-version`, `--platform` and `--python-implementation` are set your current python configuration.
However, you can download packages for different configuration as well. 

```shell
> py.lockfile -s tests/poetry.lock -t wheels/ --python-version 2.7 --platform win_amd64
📦 cffi 1.15.1  cffi-1.15.1-cp27-cp27m-win_amd64.whl
```

## Download packages from a private repository
Credentials are automatically loaded from `pypoetry/auth.toml`, `pyproject.toml` 
or we can overwrite them by environment variables.
```shell
PYLF_<REPO_NAME>_USERNAME=user PYLF_<REPO_NAME>_PASSWORD=password  py.lockfile ...
```

Optionally, we can set `PYLF_<REPO_NAME>_URL` as well, for appending custom pypi
entry point.
