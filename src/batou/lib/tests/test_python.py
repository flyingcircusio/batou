from batou.lib.python import Package, VirtualEnv, PIP
import mock
import pytest
import unittest


class TestVirtualEnv(unittest.TestCase):

    def virtualenv(self, *args, **kw):
        virtualenv = VirtualEnv(*args, **kw)
        return virtualenv

    def test_detect_should_use_version_specific_virtualenv_if_available(self):
        virtualenv = self.virtualenv('7.25')
        virtualenv.cmd = mock.Mock(return_value='')
        self.assertEqual(
            'virtualenv-7.25 --no-site-packages',
            virtualenv._detect_virtualenv())

    def test_detect_should_use_non_version_spec_venv_if_no_specific_available(
            self):
        virtualenv = self.virtualenv('7.25')
        virtualenv.cmd = mock.Mock(side_effect=[RuntimeError(), ''])
        self.assertEqual(
            'virtualenv --no-site-packages --python python7.25',
            virtualenv._detect_virtualenv())

    def test_detect_should_raise_RuntimeError_if_no_virtualenv_available(self):
        virtualenv = self.virtualenv('7.25')
        virtualenv.cmd = mock.Mock(side_effect=RuntimeError())
        with self.assertRaises(RuntimeError):
            virtualenv._detect_virtualenv()

    def test_update_should_call_executable_provided_by_detect(self):
        virtualenv = self.virtualenv('7.25')
        virtualenv.cmd = mock.Mock()
        virtualenv._detect_virtualenv = mock.Mock(
            return_value='virtualenv-executable arguments')
        virtualenv.update()
        virtualenv.cmd.assert_called_with(
            'virtualenv-executable arguments .')


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
    pip = PIP('1.3')
    pip.update()
    distribute = Package('distribute', version='0.6.34', timeout=10)
    distribute.update()
    setuptools = Package('setuptools', version='0.9.8', timeout=10)
    setuptools.update()
    # We can't simply call verify, since distribute *still* manages to
    # manipulate the installation process and update itself, so our version
    # number is ignored and we get the most recent setuptools. *le major sigh*
    assert 'distribute-' not in setuptools.cmd(
        'bin/python -c "import setuptools; print setuptools.__file__"')[0]
