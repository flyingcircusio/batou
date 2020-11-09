from batou.component import Component, ComponentDefinition
from batou.environment import Environment
import batou.utils
import os
import pytest
import subprocess


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
    root = environment.add_root(compdef.name, "host")
    root.prepare()
    root.component.deploy()
    return root


@pytest.yield_fixture(autouse=True)
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


def pytest_cmdline_main(config):
    import sys
    import pytest_black

    def new_runtest(self):
        executable = os.path.join(os.path.dirname(sys.executable), "black")
        cmd = [
            executable,
            "--check",
            "--diff",
            "--quiet",
            str(self.fspath),
        ]
        try:
            subprocess.run(
                cmd, check=True, stdout=subprocess.PIPE, universal_newlines=True
            )
        except subprocess.CalledProcessError as e:
            raise pytest_black.BlackError(e)

        mtimes = getattr(self.config, "_blackmtimes", {})
        mtimes[str(self.fspath)] = self._blackmtime

    pytest_black.BlackItem.runtest = new_runtest
