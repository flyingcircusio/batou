# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.service import Service, ServiceConfig
import batou.tests
import os.path
import unittest


class ServiceTests(unittest.TestCase):

    def test_datastructures_init(self):
        service1 = Service()
        service2 = Service()
        self.assertIsNot(service1.components, service2.components)
        self.assertIsNot(service1.environments, service2.environments)

class ServiceConfigTest(batou.tests.TestCase):

    def setUp(self):
        self.fixture = os.path.dirname(__file__) + '/fixture/ordering'
        self.config = ServiceConfig(self.fixture, ['test'])
        self.config.scan()

    def test_config_should_define_component_order(self):
        env = self.config.service.environments['test']
        self.config.configure_components(env)
        components = env.hosts['localhost'].components
        self.assertEqual([c.name for c in components], ['c1', 'c2', 'c3'])
