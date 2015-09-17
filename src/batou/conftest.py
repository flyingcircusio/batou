from batou.component import Component, ComponentDefinition
from batou.environment import Environment
import os
import pytest


@pytest.fixture
def root(tmpdir):
    environment = Environment('test', basedir=str(tmpdir))
    environment._set_defaults()
    os.chdir(str(tmpdir))

    class MyComponent(Component):
        pass

    compdef = ComponentDefinition(MyComponent)
    compdef.defdir = str(tmpdir)
    environment.components[compdef.name] = compdef
    root = environment.add_root(compdef.name, 'host')
    root.prepare()
    root.component.deploy()
    return root


@pytest.yield_fixture(autouse=True)
def ensure_workingdir(request):
    working_dir = os.getcwd()
    yield
    os.chdir(working_dir)


def pytest_assertrepr_compare(op, left, right):
    if left.__class__.__name__ == 'Ellipsis':
        return left.compare(right).diff
    elif right.__class__.__name__ == 'Ellipsis':
        return right.compare(left).diff
