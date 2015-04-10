from batou.component import Component
from batou.environment import Environment
from batou import MissingEnvironment
import os
import os.path
import pwd
import pytest


def test_parse_nonexisting_environment_raises_error(tmpdir):
    env = Environment('test', basedir=str(tmpdir))
    with pytest.raises(MissingEnvironment):
        env.load()


@pytest.fixture
def env():
    environment = Environment(
        'dev', basedir=os.path.dirname(__file__) + '/fixture/basic_service')
    environment.load()
    return environment


@pytest.fixture
def env_prod():
    environment = Environment(
        'production',
        basedir=os.path.dirname(__file__) + '/fixture/basic_service')
    environment.load()
    return environment


def test_service_options_are_set(env):
    assert env.base_dir.endswith('/fixture/basic_service')


def test_components_are_fully_loaded(env):
    assert sorted(env.components) == ['zeo', 'zope']


def test_production_environment_is_loaded(env_prod):
    assert env_prod.service_user == 'alice'
    assert env_prod.branch == 'production'
    assert env_prod.host_domain == 'example.com'

    assert sorted(env_prod.hosts) == [
        'host1.example.com', 'host2.example.com', 'host3.example.com']

    host1 = env_prod.hosts['host1.example.com']
    assert host1.name == 'host1'
    assert host1.fqdn == 'host1.example.com'
    host1_components = [x.name for x in env_prod.root_components
                        if x.host is host1]
    assert host1_components == ['zope']


def test_dev_environment_is_loaded(env):
    assert pwd.getpwuid(os.getuid()).pw_name == env.service_user
    assert env.branch == 'default'
    assert env.host_domain is None
    assert set(env.hosts.keys()) == set(['localhost', 'host2'])

    localhost = env.hosts['localhost']
    assert localhost.name == 'localhost'
    assert localhost.fqdn == 'localhost'
    root_components = set(
        [x.name for x in env.root_components if x.host is localhost])
    assert root_components == set(['zeo', 'zope'])

    zeo = env.get_root('zeo', 'localhost')
    zeo.prepare()
    assert isinstance(zeo.component, Component)
    assert zeo.name == 'zeo'
    assert zeo.component.port == 9001


def test_component_has_features_set(env):
    env.configure()
    # The localhost ZEO doesn't specify features and thus gets all set
    zeo1 = env.get_root('zeo', 'localhost').component
    assert zeo1.features == ['test', 'test2']

    # ZEO on host2 has selected only 'test'
    zeo2 = env.get_root('zeo', 'host2').component
    assert zeo2.features == ['test']


def test_load_environment_with_overrides(env):
    env.overrides['zeo'] = {'port': '9002'}
    env.configure()
    zeo = env.get_root('zeo', 'localhost').component
    assert zeo.port == 9002
