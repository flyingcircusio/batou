from batou.component import Component
from batou.lib.python import VirtualEnv, Package
from batou.update import update_bootstrap
from batou.utils import cmd
import os
import os.path
import pytest


@pytest.mark.slow
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
    stdout, stderr = cmd('./batou local dev localhost')
    for line in filter(None, stdout.split('\n')):
        assert line.startswith('Updating Py')
    assert "Updating Py24 >" in stdout
    assert "Updating Py25 >" in stdout
    assert "Updating Py26 >" in stdout
    assert "Updating Py27 >" in stdout
    assert "Updating Py31 >" in stdout
    assert "Updating Py32 >" in stdout
    assert "Updating Py33 >" in stdout
    assert stderr == ""


@pytest.mark.slow
@pytest.mark.timeout(60)
def test_updates_old_distribute_to_setuptools(root):
    class Playground(Component):
        def configure(self):
            self.venv = VirtualEnv('2.7')
            self += self.venv

    distribute = Package('distribute', version='0.6.34', timeout=10)
    setuptools = Package('setuptools', version='0.9.8', timeout=10)

    playground = Playground()
    root.component += playground
    playground.venv += distribute
    playground.deploy()

    playground.venv.sub_components.remove(distribute)
    playground.venv += setuptools
    playground.deploy()

    # We can't simply call verify, since distribute *still* manages to
    # manipulate the installation process and update itself, so our version
    # number is ignored and we get the most recent setuptools. *le major sigh*
    assert 'distribute-' not in playground.cmd(
        playground.workdir + '/bin/python -c '
        '"import setuptools; print setuptools.__file__"')[0]
