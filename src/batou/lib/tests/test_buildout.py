# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import mock
import unittest


class TestBuildout(unittest.TestCase):

    def buildout(self, **kw):
        from ..buildout import Buildout
        buildout = Buildout(**kw)
        buildout.cmd = mock.Mock()
        return buildout

    def test_configure_should_store_config_path(self):
        from ..file import File
        # Prepare buildout
        buildout = self.buildout(config=File('foo.cfg'))
        # set magic value which is expected to appear on the other side
        with mock.patch('batou.component.Component.__add__'):
            buildout.configure()
        self.assertEqual('foo.cfg', buildout.config_file_name)

    def test_update_should_pass_config_file_name(self):
        buildout = self.buildout()
        buildout.config_file_name = 'myown.cfg'
        buildout.update()
        buildout.cmd.assert_any_call(
            'bin/buildout -t 3 -c "myown.cfg" bootstrap')
        buildout.cmd.assert_any_call(
            'bin/buildout -t 3 -c "myown.cfg"')
