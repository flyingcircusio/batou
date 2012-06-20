# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.host import Host
from batou.tests import TestCase
import mock


class Component(object):

    def deploy(self):
        pass


class HostTest(TestCase):

    def test_host_deploys_all_registered_components(self):
        host = Host('h1', 'env')
        component = mock.Mock()
        host.components.append(component)
        host.deploy()
        self.assertTrue(component.deploy.called)
