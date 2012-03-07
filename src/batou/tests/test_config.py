# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.component import Component
from batou.service import ServiceConfig
import os
import os.path
import pwd
import unittest


class BrokenConfigTests(unittest.TestCase):

    def test_parse_nonexisting_file_raises_ioerror(self):
        with self.assertRaises(IOError):
            ServiceConfig(os.path.dirname(__file__) +
                          '/no/such/file.cfg', ['foo'])


class ConfigTestsBasicScenario(unittest.TestCase):

    def setUp(self):
        self.config = ServiceConfig(os.path.dirname(__file__) +
                   '/fixture/basic_service', ['dev'])
        self.config.scan()
        for env in self.config.service.environments.values():
            self.config.configure_components(env)
        self.service = self.config.service

    def test_service_options_are_set(self):
        self.assertTrue(self.service.base.endswith(
            '/fixture/basic_service'))

    def test_components_are_fully_loaded(self):
        self.assertEquals(['zeo', 'zope'], sorted(self.service.components))

    def test_dev_is_loaded_but_production_is_not(self):
        self.assertEquals(['dev'],
                          sorted(self.service.environments))

    def test_production_environment_is_loaded(self):
        self.config.environments = set(['production'])
        self.config.scan()
        self.config.configure_components(
            self.config.service.environments['production'])
        production = self.service.environments['production']
        self.assertEquals('alice', production.service_user)
        self.assertEquals('production', production.branch)
        self.assertEquals('example.com', production.host_domain)

        self.assertEquals(['host1.example.com', 'host2.example.com',
                           'host3.example.com'],
                          sorted(production.hosts))

        host1 = production.hosts['host1.example.com']
        self.assertEqual('host1', host1.name)
        self.assertEqual('host1.example.com', host1.fqdn)
        self.assertEqual(1, len(host1.components))
        zope = host1.components[0]
        self.assertIsInstance(zope, Component)
        self.assertEqual('zope', zope.name)

    def test_dev_environment_is_loaded(self):
        dev = self.service.environments['dev']
        self.assertEquals(pwd.getpwuid(os.getuid()).pw_name, dev.service_user)
        self.assertEquals('default', dev.branch)
        self.assertEquals(None, dev.host_domain)

        self.assertEquals(['localhost'], sorted(dev.hosts))

        localhost = dev.hosts['localhost']
        self.assertEqual('localhost', localhost.name)
        self.assertEqual('localhost', localhost.fqdn)
        components = list(localhost.components)
        components.sort(key=lambda x:x.name)
        self.assertEqual(['zeo', 'zope'], [x.name for x in components])
        zeo = components[0]
        self.assertIsInstance(zeo, Component)
        self.assertEqual('zeo', zeo.name)

    def test_component_has_features_set(self):
        dev = self.service.environments['dev']
        self.assertEquals(['test'],
                          dev.hosts['localhost'].components[1].features)
