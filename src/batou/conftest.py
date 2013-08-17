from batou.component import Component
from batou.environment import Environment
import os
import pytest


@pytest.fixture
def root(tmpdir):
    environment = Environment('test', str(tmpdir))
    environment._set_defaults()
    os.chdir(str(tmpdir))

    class MyComponent(Component):
        defdir = str(tmpdir)
    environment.components['mycomponent'] = MyComponent
    root = environment.add_root('mycomponent', 'host')
    root.prepare()
    root.component.deploy()
    return root


@pytest.fixture(scope='session', autouse=True)
def ensure_workingdir(request):
    working_dir = os.getcwd()

    def go_back():
        os.chdir(working_dir)
    request.addfinalizer(go_back)
