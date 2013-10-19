import os
import pytest
import shutil


@pytest.fixture()
def sample_service(tmpdir):
    shutil.copytree(os.path.dirname(__file__)+'/fixture/sample_service',
                    str(tmpdir / 'sample_service'))
    os.chdir(str(tmpdir / 'sample_service'))
