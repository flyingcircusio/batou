from batou.environment import Environment
from batou import MissingEnvironment
from mock import Mock
import pytest


def test_environment_should_raise_if_no_config_file(tmpdir):
    e = Environment(u'foobar')
    with pytest.raises(MissingEnvironment):
        e.load()


def test_load_should_use_defaults(sample_service):
    e = Environment(u'test-without-env-config')
    e.load()
    assert e.host_domain is None
    assert e.branch is None


def test_load_should_use_config(sample_service):
    e = Environment(u'test-with-env-config')
    e.load()
    assert e.service_user == u'joe'
    assert e.host_domain == u'example.com'
    assert e.branch == u'release'


def test_load_ignores_predefined_environment_settings(sample_service):
    e = Environment(u'test-with-env-config')
    e.service_user = u'bob'
    e.host_domain = u'sample.com'
    e.branch = u'default'
    e.load()
    assert e.service_user == u'bob'
    assert e.host_domain == u'sample.com'
    assert e.branch == u'default'


def test_load_sets_up_overrides(sample_service):
    e = Environment('test-with-overrides')
    e.load()
    assert e.overrides == {'hello1': {'asdf': '1'}}


def test_loads_configures_vfs_sandbox(sample_service):
    e = Environment('test-with-vfs-sandbox')
    e.load()
    assert e.vfs_sandbox.map('/asdf').endswith('work/_/asdf')
    assert e.map('/asdf').endswith('work/_/asdf')


def test_default_sandbox_is_identity():
    e = Environment(u'foo')
    assert e.map('/asdf') == '/asdf'


def test_get_host_raises_keyerror_if_unknown():
    e = Environment(u'name')
    with pytest.raises(KeyError):
        e.get_host('asdf')


def test_get_host_normalizes_hostname():
    e = Environment(u'name')
    e.hosts['asdf.example.com'] = host = Mock()
    e.host_domain = 'example.com'
    assert host == e.get_host('asdf')
    assert host == e.get_host('asdf.example.com')


def test_normalize_hostname_regression_11156():
    # The issue here was that we used "rstrip" which works on characters,
    # not substrings. Having the domain (example.com) start with an eee
    # causes the hostname to get stripped of it's "eee"s ending in an
    # empty hostname accidentally.
    e = Environment(u'name')
    e.hosts['eee.example.com'] = host = Mock()
    e.host_domain = 'example.com'
    assert host == e.get_host('eee')


def test_get_host_without_subdomain_also_works():
    e = Environment(u'name')
    e.hosts['example.com'] = host = Mock()
    e.host_domain = 'example.com'
    assert host == e.get_host('example.com')


def test_get_root_raises_keyerror_on_nonassigned_component():
    e = Environment(u'foo')
    with pytest.raises(KeyError):
        e.get_root('asdf', 'localhost')


def test_multiple_components(sample_service):
    e = Environment(u'test-multiple-components')
    e.load()
    components = dict(
        (host, list(sorted(c.name for c in e.roots_in_order(host=host))))
        for host in sorted(e.hosts.keys()))
    assert components == dict(
        localhost=['hello1', 'hello2'],
        otherhost=['hello3', 'hello4'],
        thishost=['hello5', 'hello6'])


def test_parse_host_components():
    from batou.environment import parse_host_components
    assert (parse_host_components(['asdf']) ==
            {'asdf': {'features': [], 'ignore': False}})

    assert (parse_host_components(['!asdf']) ==
            {'asdf': {'features': [], 'ignore': True}})

    assert (parse_host_components(['!asdf:test', 'asdf:bar']) ==
            {'asdf': {'features': ['test', 'bar'], 'ignore': True}})

    assert (parse_host_components(['asdf:test', 'asdf:bar']) ==
            {'asdf': {'features': ['test', 'bar'], 'ignore': False}})
