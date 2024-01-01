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
        ('3.11', 'cp', 'manylinux2014_ppc64le',
         f'{PACKAGE}-cp311-cp311-manylinux_2_17_'
         f'ppc64le.manylinux2014_ppc64le.whl'),
        ('3.10', 'cp', 'musllinux_1_1_x86_64',
         f'{PACKAGE}-cp310-cp310-musllinux_1_1_x86_64.whl'),

    ]
)
def data(request):
    return request.param


def test_package(capsys, data):
    main(['--sourcefile=./poetry.lock', f'--python-version={data[0]}',
          f'--python-implementation={data[1]}', f'--platform={data[2]}',
          '--dryrun', '--no-color'])
    assert capsys.readouterr().out.strip().endswith(data[3])

    # with capsys.disabled():
    #     print(captured.out.strip())
