import pytest
import os.path
from tempfile import TemporaryDirectory


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
    with CompressionHelperTempfolder(source_folder, cmd_compress='7z a') as compressor:
        merge(
            grouped_filelist={
                'Test': {
                    'test1.txt',
                    'test2.txt',
                }
                'Another': {
                    'another.txt'
                }
            },
            compressor,
        )
    assert {'Test.7z', 'Another.7z'} in os.listdir(source_folder)
