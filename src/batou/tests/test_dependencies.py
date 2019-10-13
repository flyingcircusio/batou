from batou import CycleErrorDetected, UnknownComponentConfigurationError
from batou import UnsatisfiedResources, UnusedResources
from batou.component import Component, ComponentDefinition
from batou.environment import Environment
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
    for component in list(globals().values()):
        if not isinstance(component, type):
            continue
        if issubclass(component, Component):
            compdef = ComponentDefinition(component)
            env.components[compdef.name] = compdef
    return env


def test_provider_without_consumer_raises_error(env):
    env.add_root('provider', 'host')
    with pytest.raises(UnusedResources):
        env.configure()


def test_consumer_retrieves_value_from_provider_order1(env):
    provider = env.add_root('provider', 'test')
    consumer = env.add_root('consumer', 'test')
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert env.root_dependencies() == {
        provider: set(), consumer: {provider}}


def test_provider_with_consumer_limited_by_host_raises_error(env):
    env.add_root('provider', 'test2')
    env.add_root('samehostconsumer', 'test')
    with pytest.raises(UnusedResources):
        env.configure()


def test_consumer_retrieves_value_from_provider_order2(env):
    consumer = env.add_root('consumer', 'host')
    provider = env.add_root('provider', 'host')
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert env.root_dependencies() == {
        provider: set(), consumer: {provider}}


def test_consumer_without_provider_raises_error(env):
    env.add_root('consumer', 'host')
    with pytest.raises(Exception):
        env.configure()
    for exc in env.exceptions:
        if isinstance(exc, UnsatisfiedResources):
            assert set(['the-answer']) == set(exc.resources)
            break
    else:
        assert False, "Did not find exception"


def test_aggressive_consumer_raises_unsatisfiedrequirement(env):
    env.add_root('aggressiveconsumer', 'host')
    with pytest.raises(Exception):
        env.configure()
    for exc in env.exceptions:
        if isinstance(exc, UnsatisfiedResources):
            assert set(['the-answer']) == set(exc.resources)
            break
    else:
        assert False, "Did not find expected exception."


def test_broken_component_logs_real_exception(env):
    env.add_root('broken', 'host')
    with pytest.raises(UnknownComponentConfigurationError):
        env.configure()


def test_consumer_retrieves_value_from_provider_with_same_host(env):
    consumer = env.add_root('samehostconsumer', 'host')
    provider = env.add_root('provider', 'host')
    consumer2 = env.add_root('samehostconsumer', 'host2')
    provider2 = env.add_root('provider', 'host2')
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert list(consumer2.component.the_answer) == [42]
    assert env.root_dependencies() == {
        consumer: {provider}, provider: set(),
        consumer2: {provider2}, provider2: set()}


def test_components_are_ordered_over_multiple_hosts(env):
    provider1 = env.add_root('provider', 'host')
    provider2 = env.add_root('provider', 'host2')
    consumer1 = env.add_root('consumer', 'host')
    consumer2 = env.add_root('consumer', 'host2')
    env.configure()
    assert env.root_dependencies() == {
        consumer1: {provider1, provider2}, provider1: set(),
        consumer2: {provider1, provider2}, provider2: set()}


def test_circular_depending_component(env):
    env.add_root('circular1', 'test')
    env.add_root('circular2', 'test')
    with pytest.raises(CycleErrorDetected):
        env.configure()


def test_dirty_dependency_for_one_time_retrieval(env, capsys):
    env.add_root('circular1', 'test')
    env.add_root('dirtysingularcircularreverse', 'test')
    env.configure()
