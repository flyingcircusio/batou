from batou.environment import Environment
from mock import Mock
import unittest


class EnvironmentTest(unittest.TestCase):

    def test_configure_should_use_defaults(self):
        e = Environment(u'name', u'service')
        e.from_config({})
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

    def test_normalize_hostname_regression_11156(self):
        # The issue here was that we used "rstrip" which works on characters,
        # not substrings. Having the domain (example.com) start with an eee
        # causes the hostname to get stripped of it's "eee"s ending in an
        # empty hostname accidentally.
        e = Environment(u'name', 'service')
        e.hosts['eee.example.com'] = host = Mock()
        e.host_domain = 'example.com'
        self.assertEquals(host, e.get_host('eee'))

    def test_get_host_without_subdomain_also_works(self):
        e = Environment(u'name', 'service')
        e.hosts['example.com'] = host = Mock()
        e.host_domain = 'example.com'
        self.assertEquals(host, e.get_host('example.com'))
