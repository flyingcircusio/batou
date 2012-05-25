
import unittest
from batou.component import Component, RootComponentFactory
from batou.service import Service
from batou.environment import Environment, UnusedResource
from batou.host import Host


class Provider(Component):

    def configure(self):
        self.provide('the-answer', 42)
        self.require('the-question')


class Consumer(Component):

    def configure(self):
        self.the_answer = self.require('the-answer')


class TestDependencies(unittest.TestCase):

    def setUp(self):
        super(TestDependencies, self).setUp()
        self.service = Service()
        self.service.components['provider'] = RootComponentFactory(
                'provider', Provider, '.')
        self.service.components['consumer'] = RootComponentFactory(
                'consumer', Consumer, '.')

        self.env = Environment('test', self.service)
        self.env.hosts['test'] = self.host = Host('test', self.env)

    def test_provider_without_consumer_raises_error(self):
        self.host.add_component('provider')
        with self.assertRaises(UnusedResource):
            self.env.configure()

    def test_consumer_retrieves_value_from_provider_order1(self):
        self.host.add_component('provider')
        self.host.add_component('consumer')
        self.env.configure()
        consumer = self.host.components[1].component
        self.assertIsInstance(consumer, Consumer)
        self.assertListEqual([42], list(consumer.the_answer))

    def test_consumer_retrieves_value_from_provider_order2(self):
        self.host.add_component('consumer')
        self.host.add_component('provider')
        self.env.configure()
        consumer = self.host.components[0].component
        self.assertIsInstance(consumer, Consumer)
        self.assertListEqual([42], list(consumer.the_answer))

    def test_consumer_without_provider_raises_error(self):
        pass
