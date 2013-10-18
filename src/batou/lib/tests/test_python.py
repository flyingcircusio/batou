from batou.component import Component
from batou.lib.python import Package, VirtualEnv
import mock
import pytest


def test_package_install(root):
    package = Package('foo', version='1.2.5')
    package.cmd = mock.Mock()
    root.component += package
    package.update()
    package.cmd.assert_called_with(
        'bin/pip --timeout=3 install --egg --ignore-installed "foo==1.2.5"')


@pytest.mark.slow
@pytest.mark.timeout(60)
def test_updates_old_distribute_to_setuptools(root):
    class Playground(Component):
        def configure(self):
            self += VirtualEnv('2.7')

    distribute = Package('distribute', version='0.6.34', timeout=10)
    setuptools = Package('setuptools', version='0.9.8', timeout=10)

    playground = Playground()
    root.component += playground
    playground += distribute
    playground.deploy()

    playground.sub_components.remove(distribute)
    playground += setuptools
    playground.deploy()

    # We can't simply call verify, since distribute *still* manages to
    # manipulate the installation process and update itself, so our version
    # number is ignored and we get the most recent setuptools. *le major sigh*
    assert 'distribute-' not in playground.cmd(
        playground.workdir + '/bin/python -c '
        '"import setuptools; print setuptools.__file__"')[0]
