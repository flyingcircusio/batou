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


@pytest.mark.timeout(20)
def test_updates_old_distribute_to_setuptools(root):
    venv = VirtualEnv('2.7')
    venv.update()
    distribute = Package('distribute', version='0.6.34', timeout=10)
    distribute.update()
    setuptools = Package('setuptools', version='0.9.8', timeout=10)
    setuptools.update()
    # We can't simply call verify, since distribute *still* manages to
    # manipulate the installation process and update itself, so our version
    # number is ignored and we get the most recent setuptools. *le major sigh*
    assert 'distribute-' not in setuptools.cmd(
        'bin/python -c "import setuptools; print setuptools.__file__"')[0]
