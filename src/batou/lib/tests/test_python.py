from batou.component import Component
from batou.lib.python import VirtualEnv
from batou.update import update_bootstrap
from batou.utils import cmd
import os
import os.path
import pytest


@pytest.mark.slow
@pytest.mark.jenkinsonly
@pytest.mark.timeout(240)
def test_package_venv_installations(root):
    # this is a really nasty test ...
    base_dir = os.path.join(
        os.path.dirname(__file__), '../../../../')

    # copy the "venv" example
    cmd('cp -a {}/examples/venvs/* .'.format(base_dir))
    cmd('rm -rf work')

    # ensure the dev link is OK
    update_bootstrap('', base_dir)

    # run batou, hope for the best. ;)
    stdout, stderr = cmd('./batou deploy dev')
    assert "Deploying component py26" in stdout
    assert "Deploying component py27" in stdout
    assert "Deploying component py33" in stdout
    assert "Deploying component py34" in stdout
    assert "Deploying component py35" in stdout
    assert stderr == ""


def test_venv_updates_if_python_changes(root):
    import ast

    class Playground(Component):
        namevar = 'version'

        def configure(self):
            self.venv = VirtualEnv(self.version)
            self += self.venv

    playground = Playground('2.6')
    root.component += playground
    playground.deploy()
    root.component.sub_components.remove(playground)

    playground = Playground('2.7')
    root.component += playground
    playground.deploy()

    out, err = playground.cmd(
        '{}/bin/python -c "import sys; print sys.version_info[:2]"'.format(
            playground.workdir))
    assert (2, 7) == ast.literal_eval(out)


def test_venv_does_not_update_if_python_does_not_change(root):

    class Playground(Component):
        namevar = 'version'

        def configure(self):
            self.venv = VirtualEnv(self.version)
            self += self.venv

    playground = Playground('2.7')
    root.component += playground
    playground.deploy()
    assert playground.changed
    playground.deploy()
    assert not playground.changed
