import os

import pytest

import batou.utils
from batou.component import Component, ComponentDefinition
from batou.environment import Environment
from batou.host import Host


@pytest.fixture
def root(tmpdir):
    environment = Environment("test", basedir=str(tmpdir))
    environment._set_defaults()
    os.chdir(str(tmpdir))

    class MyComponent(Component):
        pass

    compdef = ComponentDefinition(MyComponent)
    compdef.defdir = str(tmpdir)
    environment.components[compdef.name] = compdef
    environment.hosts["localhost"] = host = Host("localhost", environment)
    root = environment.add_root(compdef.name, host)
    root.prepare()
    root.component.deploy()
    return root


@pytest.fixture(autouse=True)
def ensure_workingdir(request):
    working_dir = os.getcwd()
    yield
    os.chdir(working_dir)


def pytest_assertrepr_compare(op, left, right):
    if left.__class__.__name__ == "Ellipsis":
        return left.compare(right).diff
    elif right.__class__.__name__ == "Ellipsis":
        return right.compare(left).diff


@pytest.fixture(autouse=True)
def reset_resolve_overrides():
    batou.utils.resolve_override.clear()
    batou.utils.resolve_v6_override.clear()


@pytest.fixture(autouse=True)
def output(monkeypatch):
    from batou import output
    from batou._output import TestBackend

    backend = TestBackend()
    monkeypatch.setattr(output, 'backend', backend)
    return output
