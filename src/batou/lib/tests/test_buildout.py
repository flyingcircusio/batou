# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.lib.buildout import Buildout
from batou.tests import TestCase
import mock
import sysconfig


class BuildoutTests(TestCase):

    def test_pass(self):
        pass
    # XXX 
    #@mock.patch('os.symlink')
    #def test_determine_python_config(self, symlink):
    #    c = Buildout()
    #    c.python = 'python%s' % sysconfig.get_python_version()
    #    c._install_python_config()
    #    self.assertTrue(symlink.called)
