import os.path

import pytest
from py_lockfile import main

PACKAGE = 'cffi-1.15.1'


def test_download():
    if os.path.exists('./wheels'):
        for file in os.listdir('./wheels'):
            os.remove(f'./wheels/{file}')
        os.removedirs('./wheels')
    main([])
    assert os.path.exists('./wheels')
    for file in os.listdir('./wheels'):
        assert file.endswith('.whl')


@pytest.fixture(
    params=[
        ('2.7', 'cp', 'win_amd64', f'{PACKAGE}-cp27-cp27m-win_amd64.whl'),
        ('3.11', 'cp', 'win_amd64', f'{PACKAGE}-cp311-cp311-win_amd64.whl'),
        ('3.9', 'cp', 'macosx_11_0_arm64',
         f'{PACKAGE}-cp39-cp39-macosx_11_0_arm64.whl'),
        ('3.10', 'cp', 'macosx_10_9_x86_64',
         f'{PACKAGE}-cp310-cp310-macosx_10_9_x86_64.whl'),
        ('2.7', 'cp', 'manylinux1_i686',
         f'{PACKAGE}-cp27-cp27mu-manylinux1_i686.whl'),
        ('3.11', 'cp', 'manylinux_2_17_ppc64le',
         f'{PACKAGE}-cp311-cp311-manylinux_2_17_ppc64le.'
         f'manylinux2014_ppc64le.whl'),
        ('3.10', 'cp', 'musllinux_1_1_x86_64',
         f'{PACKAGE}-cp310-cp310-musllinux_1_1_x86_64.whl'),

    ]
)
def data(request):
    return request.param


def test_pipenv(capsys, data):
    main(['--sourcefile=./tests/Pipfile.lock', f'--python-version={data[0]}',
          f'--python-implementation={data[1]}', f'--platform={data[2]}',
          '--dryrun', '--no-color'])
    oo = capsys.readouterr().out.strip()
    assert oo.endswith(data[3])


def test_poetry(capsys, data):
    main(['--sourcefile=./tests/poetry.lock', f'--python-version={data[0]}',
          f'--python-implementation={data[1]}', f'--platform={data[2]}',
          '--dryrun', '--no-color'])
    oo = capsys.readouterr().out.strip()
    assert oo.endswith(data[3])


def test_pdm(capsys, data):
    main(['--sourcefile=./tests/pdm.lock', f'--python-version={data[0]}',
          f'--python-implementation={data[1]}', f'--platform={data[2]}',
          '--dryrun', '--no-color'])
    oo = capsys.readouterr().out.strip()
    assert oo.endswith(data[3])


def test_abi3(capsys):
    main(['--sourcefile=./tests/abi/pdm.lock', '--python-version=3.11',
          '--python-implementation=cp', '--platform=manylinux_2_28_x86_64',
          '--dryrun', '--no-color'])
    oo = capsys.readouterr().out.strip()
    assert oo.endswith('cryptography-43.0.3-cp39-abi3-manylinux_2_28_x86_64.whl')
