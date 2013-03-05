# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import mock
import unittest


class TestVirtualEnv(unittest.TestCase):

    def virtualenv(self, *args, **kw):
        from ..python import VirtualEnv
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
