# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.environment import Environment
from mock import Mock
import unittest


class EnvironmentTest(unittest.TestCase):

    def test_configure_should_use_defaults(self):
        e = Environment(u'name', u'service')
        e.from_config({})
        self.assertEqual(Environment.service_user, e.service_user)
        self.assertEqual(Environment.host_domain, e.host_domain)
        self.assertEqual(Environment.branch, e.branch)

    def test_configure_should_use_config(self):
        e = Environment(u'name', u'service')
        e.from_config(dict(
            service_user=u'joe',
            host_domain=u'example.com',
            branch=u'release'
        ))
        self.assertEqual(u'joe', e.service_user)
        self.assertEqual(u'example.com', e.host_domain)
        self.assertEqual(u'release', e.branch)

    def test_get_host_raises_keyerror_if_unknown(self):
        e = Environment(u'name', u'service')
        with self.assertRaises(KeyError):
            e.get_host('asdf')

    def test_get_host_normalizes_hostname(self):
        e = Environment(u'name', 'service')
        e.hosts['asdf.example.com'] = host = Mock()
        e.host_domain = 'example.com'
        self.assertEquals(host, e.get_host('asdf'))
        self.assertEquals(host, e.get_host('asdf.example.com'))
