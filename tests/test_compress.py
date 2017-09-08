import pytest

import os
import subprocess
from tempfile import TemporaryDirectory
from functools import partial

from ..goodMerge import CompressionHelperTempfolder, merge


@pytest.fixture
def source_folder():
    with TemporaryDirectory() as tempdir:
        _abs_path = partial(os.path.join, tempdir)

        def _create_file(filename, data):
            with open(_abs_path(filename), 'wt') as filehandle:
                filehandle.write(data)

        _create_file('test1.txt', 'test1')
        _create_file('test2.txt', 'test2')
        _create_file('another.txt', 'another')

        # Compress test1.txt in a zip file
        subprocess.call(('7z', 'a', '-tzip', _abs_path('test1.zip'), _abs_path('test1.txt')))
        os.remove(_abs_path('test1.txt'))

        yield tempdir


def test_compress(source_folder):
    """
    Compress and decompress test files based on provided group data
    (requires '7z' commandline tool)
    """
    grouped_filelist = {
        'Test': {
            'test1.zip',
            'test2.txt',
        },
        'Another': {
            'another.txt'
        }
    }

    with CompressionHelperTempfolder(source_folder) as compressor:
        merge(grouped_filelist, compressor)

    expected_filenames = {f'{key}.7z' for key in grouped_filelist.keys()}
    assert expected_filenames == set(os.listdir(source_folder))

    # Extract files and assert compressed file content
    expected_compressed_archives = {
        'Test.7z': {
            'test1.txt',
            'test2.txt',
        },
        'Another.7z': {
            'another.txt'
        }
    }
    for filename, expected_subfiles in expected_compressed_archives.items():
        subprocess.call(['7z', f'-o{source_folder}', 'e', os.path.join(source_folder, filename)])

        expected_subfiles = expected_subfiles
        new_files = set(os.listdir(source_folder)) - expected_filenames
        assert new_files == expected_subfiles
        for subfile in expected_subfiles:
            os.remove(os.path.join(source_folder, subfile))
