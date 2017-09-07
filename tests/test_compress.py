import pytest

import os
import subprocess
from tempfile import TemporaryDirectory

from ..goodMerge import CompressionHelperTempfolder, merge


@pytest.fixture
def source_folder():
    with TemporaryDirectory() as tempdir:
        def _create_file(filename, data):
            with open(os.path.join(tempdir, filename), 'wt') as filehandle:
                filehandle.write(data)

        _create_file('test1.txt', 'test1')
        _create_file('test2.txt', 'test2')
        _create_file('another.txt', 'another')

        yield tempdir


def test_compress(source_folder):
    """
    Compress and decompress test files based on provided group data
    (requires '7z' commandline tool)
    """
    grouped_filelist = {
        'Test': {
            'test1.txt',
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
    for filename, expected_subfiles in grouped_filelist.items():
        subprocess.call(['7z', f'-o{source_folder}', 'e', os.path.join(source_folder, f'{filename}.7z')])

        expected_subfiles = expected_subfiles
        new_files = set(os.listdir(source_folder)) - expected_filenames
        assert new_files == expected_subfiles
        for subfile in expected_subfiles:
            os.remove(os.path.join(source_folder, subfile))
