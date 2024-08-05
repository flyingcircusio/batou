import pytest

from batou import (
    CycleErrorDetected,
    NonConvergingWorkingSet,
    UnknownComponentConfigurationError,
    UnsatisfiedResources,
    UnusedResources,
)
from batou.component import Component, ComponentDefinition
from batou.environment import Environment
from batou.host import Host


class Provider(Component):
    def configure(self):
        self.provide("the-answer", 42)


class Consumer(Component):
    def configure(self):
        self.the_answer = self.require("the-answer")


class AggressiveConsumer(Component):
    def configure(self):
        self.the_answer = self.require("the-answer")[0]


class SameHostConsumer(Component):
    def configure(self):
        self.the_answer = self.require("the-answer", self.host)


class Broken(Component):
    def configure(self):
        raise KeyError("foobar")


class Circular1(Component):
    def configure(self):
        self.asdf = self.require("asdf")
        self.provide("bsdf", self)


class Circular2(Component):
    def configure(self):
        self.bsdf = self.require("bsdf")
        self.provide("asdf", self)


class DirtySingularCircularReverse(Component):
    def configure(self):
        self.bsdf = self.require("bsdf", reverse=True, dirty=True)
        self.provide("asdf", self)


@pytest.fixture
def env():
    env = Environment("test")
    for component in list(globals().values()):
        if not isinstance(component, type):
            continue
        if issubclass(component, Component):
            compdef = ComponentDefinition(component)
            env.components[compdef.name] = compdef
    return env


def test_provider_without_consumer_raises_error(env):
    env.add_root("provider", Host("host", env))
    errors = env.configure()
    assert len(errors) == 1
    assert isinstance(errors[0], UnusedResources)


def test_consumer_retrieves_value_from_provider_order1(env):
    provider = env.add_root("provider", Host("test", env))
    consumer = env.add_root("consumer", Host("test", env))
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert env.root_dependencies() == {provider: set(), consumer: {provider}}


def test_provider_with_consumer_limited_by_host_raises_error(env):
    env.add_root("provider", Host("test2", env))
    env.add_root("samehostconsumer", Host("test", env))
    errors = env.configure()
    assert len(errors) == 3
    assert isinstance(errors[0], UnsatisfiedResources)
    assert isinstance(errors[1], NonConvergingWorkingSet)
    assert isinstance(errors[2], UnusedResources)


def test_consumer_retrieves_value_from_provider_order2(env):
    consumer = env.add_root("consumer", Host("host", env))
    provider = env.add_root("provider", Host("host", env))
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert env.root_dependencies() == {provider: set(), consumer: {provider}}


def test_consumer_without_provider_raises_error(env):
    env.add_root("consumer", Host("host", env))
    assert len(env.configure()) > 0
    for exc in env.exceptions:
        if isinstance(exc, UnsatisfiedResources):
            assert set(["the-answer"]) == set(
                [key for key, _ in exc.unsatisfied_resources]
            )
            break
    else:
        assert False, "Did not find exception"


def test_aggressive_consumer_raises_unsatisfiedrequirement(env):
    env.add_root("aggressiveconsumer", Host("host", env))
    assert len(env.configure()) > 0
    for exc in env.exceptions:
        if isinstance(exc, UnsatisfiedResources):
            assert set(["the-answer"]) == set(
                [key for key, _ in exc.unsatisfied_resources]
            )
            break
    else:
        assert False, "Did not find expected exception."


def test_broken_component_logs_real_exception(env):
    env.add_root("broken", Host("host", env))
    errors = env.configure()
    assert len(errors) == 2
    # could be either one of the two exceptions
    error_types = (UnknownComponentConfigurationError, NonConvergingWorkingSet)
    assert isinstance(errors[0], error_types)
    assert isinstance(errors[1], error_types)


def test_consumer_retrieves_value_from_provider_with_same_host(env):
    host = Host("host", env)
    host2 = Host("host2", env)

    consumer = env.add_root("samehostconsumer", host)
    provider = env.add_root("provider", host)
    consumer2 = env.add_root("samehostconsumer", host2)
    provider2 = env.add_root("provider", host2)
    env.configure()
    assert list(consumer.component.the_answer) == [42]
    assert list(consumer2.component.the_answer) == [42]
    assert env.root_dependencies() == {
        consumer: {provider},
        provider: set(),
        consumer2: {provider2},
        provider2: set(),
    }


def test_components_are_ordered_over_multiple_hosts(env):
    provider1 = env.add_root("provider", Host("host", env))
    provider2 = env.add_root("provider", Host("host2", env))
    consumer1 = env.add_root("consumer", Host("host", env))
    consumer2 = env.add_root("consumer", Host("host2", env))
    env.configure()
    assert env.root_dependencies() == {
        consumer1: {provider1, provider2},
        provider1: set(),
        consumer2: {provider1, provider2},
        provider2: set(),
    }


def test_circular_depending_component(env):
    env.add_root("circular1", Host("test", env))
    env.add_root("circular2", Host("test", env))
    errors = env.configure()
    assert len(errors) == 2
    error_types = (CycleErrorDetected, NonConvergingWorkingSet)
    assert isinstance(errors[0], error_types)
    assert isinstance(errors[1], error_types)


def test_dirty_dependency_for_one_time_retrieval(env, capsys):
    env.add_root("circular1", Host("test", env))
    env.add_root("dirtysingularcircularreverse", Host("test", env))
    env.configure()
