
from batou import NonConvergingWorkingSet, UnusedResource
from batou.component import Component, RootComponentFactory
from batou.environment import Environment
from batou.host import Host
from batou.service import Service
import mock
import unittest


class Provider(Component):

    def configure(self):
        self.provide('the-answer', 42)


class Consumer(Component):

    def configure(self):
        self.the_answer = self.require('the-answer')


class AggressiveConsumer(Component):

    def configure(self):
        self.the_answer = self.require('the-answer')[0]


class SameHostConsumer(Component):

    def configure(self):
        self.the_answer = self.require('the-answer', self.host)


class Broken(Component):

    def configure(self):
        raise KeyError('foobar')


class TestDependencies(unittest.TestCase):

    def setUp(self):
        super(TestDependencies, self).setUp()
        self.service = Service()
        self.service.components['provider'] = RootComponentFactory(
                'provider', Provider, '.')
        self.service.components['consumer'] = RootComponentFactory(
                'consumer', Consumer, '.')
        self.service.components['aggressiveconsumer'] = RootComponentFactory(
                'aggressiveconsumer', AggressiveConsumer, '.')
        self.service.components['samehostconsumer'] = RootComponentFactory(
                'somehostconsumer', SameHostConsumer, '.')
        self.service.components['broken'] = RootComponentFactory(
                'broken', Broken, '.')

        self.env = Environment('test', self.service)
        self.env.hosts['test'] = self.host = Host('test', self.env)
        self.env.hosts['test2'] = self.host2 = Host('test2', self.env)

    def test_provider_without_consumer_raises_error(self):
        self.host.add_component('provider')
        with self.assertRaises(UnusedResource):
            self.env.configure()

    def test_consumer_retrieves_value_from_provider_order1(self):
        provider = self.host.add_component('provider')
        consumer = self.host.add_component('consumer')
        self.env.configure()
        self.assertListEqual([42], list(consumer.component.the_answer))
        self.assertListEqual(
                [provider, consumer],
                self.env.ordered_components)

    def test_consumer_retrieves_value_from_provider_order2(self):
        consumer = self.host.add_component('consumer')
        provider = self.host.add_component('provider')
        self.env.configure()
        self.assertListEqual([42], list(consumer.component.the_answer))
        self.assertListEqual(
                [provider, consumer],
                self.env.ordered_components)

    def test_consumer_without_provider_raises_error(self):
        self.host.add_component('consumer')
        with self.assertRaises(NonConvergingWorkingSet) as e:
            self.env.configure()
        self.assertEquals(set(self.host.components), e.exception.args[0])

    def test_aggressive_consumer_raises_unsatisfiedrequirement(self):
        self.host.add_component('aggressiveconsumer')
        with self.assertRaises(NonConvergingWorkingSet) as e:
            self.env.configure()
        self.assertEquals(set(self.host.components), e.exception.args[0])

    @mock.patch('batou.environment.logger.exception')
    def test_broken_component_logs_real_exception(self, exception_log):
        self.host.add_component('broken')
        with self.assertRaises(NonConvergingWorkingSet):
            self.env.configure()
        self.assertTrue(exception_log.called)
        self.assertIsInstance(exception_log.call_args[0][0], KeyError)

    def test_consumer_retrieves_value_from_provider_with_same_host(self):
        consumer = self.host.add_component('samehostconsumer')
        provider = self.host.add_component('provider')
        provider2 = self.host2.add_component('provider')
        self.env.configure()
        self.assertListEqual([42], list(consumer.component.the_answer))
        self.assertEquals(
            [provider2, provider, consumer], self.env.ordered_components)

    def test_components_are_ordered_over_multiple_hosts(self):
        provider1 = self.host.add_component('provider')
        provider2 = self.host2.add_component('provider')
        consumer1 = self.host.add_component('consumer')
        consumer2 = self.host2.add_component('consumer')
        self.env.configure()
        self.assertEquals(
            set([provider1, provider2]),
            set(self.env.ordered_components[:2]))
        self.assertEquals(
            set([consumer1, consumer2]),
            set(self.env.ordered_components[2:]))
