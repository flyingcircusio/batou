from batou import NonConvergingWorkingSet, UnusedResource
from batou.component import Component
from batou.environment import Environment
from batou.utils import CycleError
import mock
import pytest


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


class Circular1(Component):

    def configure(self):
        self.asdf = self.require('asdf')
        self.provide('bsdf', self)


class Circular2(Component):

    def configure(self):
        self.bsdf = self.require('bsdf')
        self.provide('asdf', self)


class DirtySingularCircularReverse(Component):

    def configure(self):
        self.bsdf = self.require('bsdf', reverse=True, dirty=True)
        self.provide('asdf', self)


@pytest.fixture
def env():
    env = Environment('test')
    for component in globals().values():
        if not isinstance(component, type):
            continue
        if issubclass(component, Component):
            env.components[component.__name__.lower()] = component
    return env


def test_provider_without_consumer_raises_error(env):
    env.add_root('provider', 'host')
    with pytest.raises(UnusedResource):
        env.configure()


def test_consumer_retrieves_value_from_provider_order1(env):
    provider = env.add_root('provider', 'test')
    consumer = env.add_root('consumer', 'test')
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert env.roots_in_order() == [provider, consumer]


def test_provider_with_consumer_limited_by_host_raises_error(env):
    env.add_root('provider', 'test2')
    env.add_root('samehostconsumer', 'test')
    with pytest.raises(UnusedResource):
        env.configure()


def test_consumer_retrieves_value_from_provider_order2(env):
    consumer = env.add_root('consumer', 'host')
    provider = env.add_root('provider', 'host')
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert env.roots_in_order() == [provider, consumer]


def test_consumer_without_provider_raises_error(env):
    consumer = env.add_root('consumer', 'host')
    with pytest.raises(NonConvergingWorkingSet) as e:
        env.configure()
    assert set([consumer]) == e.value.args[0]


def test_aggressive_consumer_raises_unsatisfiedrequirement(env):
    consumer = env.add_root('aggressiveconsumer', 'host')
    with pytest.raises(NonConvergingWorkingSet) as e:
        env.configure()
    assert set([consumer]) == e.value.args[0]


@mock.patch('batou.environment.logger.error')
def test_broken_component_logs_real_exception(exception_log, env):
    env.add_root('broken', 'host')
    with pytest.raises(NonConvergingWorkingSet):
        env.configure()
    assert exception_log.called
    assert isinstance(
        exception_log.call_args_list[0][1]['exc_info'][1], KeyError)


def test_consumer_retrieves_value_from_provider_with_same_host(env):
    consumer = env.add_root('samehostconsumer', 'host')
    provider = env.add_root('provider', 'host')
    consumer2 = env.add_root('samehostconsumer', 'host2')
    provider2 = env.add_root('provider', 'host2')
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert list(consumer2.component.the_answer) == [42]
    components = env.roots_in_order()
    assert set([provider2, provider]) == set(components[:2])
    assert set([consumer, consumer2]) == set(components[2:])


def test_components_are_ordered_over_multiple_hosts(env):
    provider1 = env.add_root('provider', 'host')
    provider2 = env.add_root('provider', 'host2')
    consumer1 = env.add_root('consumer', 'host')
    consumer2 = env.add_root('consumer', 'host2')
    env.configure()
    components = env.roots_in_order()
    assert set([provider1, provider2]) == set(components[:2])
    assert set([consumer1, consumer2]) == set(components[2:])


def test_circular_depending_component(env):
    env.add_root('circular1', 'test')
    env.add_root('circular2', 'test')
    with pytest.raises(CycleError):
        env.configure()


def test_dirty_dependency_for_one_time_retrieval(env, capsys):
    env.add_root('circular1', 'test')
    env.add_root('dirtysingularcircularreverse', 'test')
    env.configure()
