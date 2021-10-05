import os
import os.path

import pytest

import batou
from batou import MissingEnvironment
from batou.component import Component
from batou.environment import Environment


def test_parse_nonexisting_environment_raises_error(tmpdir):
    environment = Environment("test", basedir=str(tmpdir))
    with pytest.raises(MissingEnvironment):
        environment.load()


@pytest.fixture
def env():
    environment = Environment(
        "dev", basedir=os.path.dirname(__file__) + "/fixture/basic_service")
    environment.load()
    return environment


@pytest.fixture
def env_prod():
    environment = Environment(
        "production",
        basedir=os.path.dirname(__file__) + "/fixture/basic_service")
    environment.load()
    return environment


def test_service_options_are_set(env):
    assert env.base_dir.endswith("/fixture/basic_service")


def test_components_are_fully_loaded(env):
    assert sorted(env.components) == ["zeo", "zope"]


def test_production_environment_is_loaded(env_prod):
    assert env_prod.service_user == "alice"
    assert env_prod.branch == "production"
    assert env_prod.host_domain == "example.com"

    assert sorted(env_prod.hosts) == [
        "host1",
        "host2",
        "host3", ]

    host1 = env_prod.hosts["host1"]
    assert host1.name == "host1"
    assert host1.fqdn == "host1.example.com"
    assert host1.service_user == "alice"
    host1_components = [
        x.name for x in env_prod.root_components if x.host is host1]
    assert host1_components == ["zope"]


def test_dev_environment_is_loaded(env):
    assert env.branch == "default"
    assert env.host_domain is None
    assert set(env.hosts.keys()) == set(["localhost", "host2"])

    localhost = env.hosts["localhost"]
    assert localhost.name == "localhost"
    assert localhost.fqdn == "localhost"
    root_components = set([
        x.name for x in env.root_components if x.host is localhost])
    assert root_components == set(["zeo", "zope"])

    zeo = env.get_root("zeo", env.hosts["localhost"])
    zeo.prepare()
    assert isinstance(zeo.component, Component)
    assert zeo.name == "zeo"
    assert zeo.component.port == 9001


def test_component_has_features_set(env):
    env.configure()
    # The localhost ZEO doesn't specify features and thus gets all set
    zeo1 = env.get_root("zeo", env.hosts["localhost"]).component
    assert zeo1.features == ["test", "test2"]

    # ZEO on host2 has selected only 'test'
    zeo2 = env.get_root("zeo", env.hosts["host2"]).component
    assert zeo2.features == ["test"]


def test_load_environment_with_overrides(env):
    env.overrides["zeo"] = {"port": "9002"}
    env.configure()
    zeo = env.get_root("zeo", env.hosts["localhost"]).component
    assert zeo.port == 9002


def test_config_exceptions_orderable(env):
    env.configure()
    c = env.get_root("zeo", env.hosts['localhost']).component

    import sys

    try:
        raise ValueError("Test")
    except Exception:
        exc_type, ex, tb = sys.exc_info()

    exceptions = [
        batou.ConfigurationError("test", None),
        batou.ConfigurationError("test", c),
        batou.ConversionError(c, "key", 123, int, "invalid int"),
        batou.MissingOverrideAttributes(c, ["sadf"]),
        batou.DuplicateComponent(c.root, c.root),
        batou.UnknownComponentConfigurationError(c.root, ex, tb),
        batou.UnusedResources({"asdf": [(c.root, 1)]}),
        batou.UnsatisfiedResources({"asdf": [c.root]}),
        batou.MissingEnvironment(env),
        batou.MissingComponent("asdf", "localhost"),
        batou.SuperfluousSection("asdf"),
        batou.SuperfluousComponentSection("asdf"),
        batou.SuperfluousSecretsSection("asdf"),
        batou.CycleErrorDetected(ValueError()),
        batou.NonConvergingWorkingSet([c]),
        batou.DeploymentError(),
        batou.DuplicateHostMapping("host", "map1", "map2"),
        batou.RepositoryDifferentError("asdf", "bsdf"),
        batou.DuplicateHostError("localhost"),
        batou.InvalidIPAddressError("asdf"), ]

    # Ensure all exceptions can be compared
    for x in exceptions:
        for y in exceptions:
            x.sort_key < y.sort_key


def test_remote_pdb_config():
    """There are some environment variables set with default values."""
    assert os.environ["PYTHONBREAKPOINT"] == "remote_pdb.set_trace"
    assert os.environ["REMOTE_PDB_HOST"] == "127.0.0.1"
    assert os.environ["REMOTE_PDB_PORT"] == "4444"
