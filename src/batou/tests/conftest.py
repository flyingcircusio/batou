import os
import pytest


@pytest.fixture(scope='session', autouse=True)
def ensure_workingdir(request):
    working_dir = os.getcwd()

    def go_back():
        os.chdir(working_dir)
    request.addfinalizer(go_back)
