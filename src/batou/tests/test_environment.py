# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.environment import Environment
import unittest


class EnvironmentTest(unittest.TestCase):

    def test_configure_should_use_defaults(self):
        e = Environment(u'name', u'service')
        e.configure({})
        self.assertEqual(Environment.service_user, e.service_user)
        self.assertEqual(Environment.host_domain, e.host_domain)
        self.assertEqual(Environment.branch, e.branch)

    def test_configure_should_use_config(self):
        e = Environment(u'name', u'service')
        e.configure(dict(
            service_user=u'joe',
            host_domain=u'example.com',
            branch=u'release'
        ))
        self.assertEqual(u'joe', e.service_user)
        self.assertEqual(u'example.com', e.host_domain)
        self.assertEqual(u'release', e.branch)
