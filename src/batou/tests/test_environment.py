from batou.environment import Environment, Config
from mock import Mock
import batou
import batou.utils
import mock
import pytest


def test_environment_should_raise_if_no_config_file(tmpdir):
    e = Environment('foobar')
    with pytest.raises(batou.MissingEnvironment):
        e.load()


def test_load_should_use_defaults(sample_service):
    e = Environment('test-without-env-config')
    e.load()
    assert e.host_domain is None
    assert e.branch is None


def test_load_should_use_config(sample_service):
    e = Environment('test-with-env-config')
    e.load()
    assert e.service_user == 'joe'
    assert e.host_domain == 'example.com'
    assert e.branch == 'release'

    assert e.hosts['foo1.example.com'].service_user == 'bob'


def test_load_ignores_predefined_environment_settings(sample_service):
    e = Environment('test-with-env-config')
    e.service_user = 'bob'
    e.host_domain = 'sample.com'
    e.branch = 'default'
    e.load()
    assert e.service_user == 'bob'
    assert e.host_domain == 'sample.com'
    assert e.branch == 'default'


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
    e = Environment('foo')
    assert e.map('/asdf') == '/asdf'


def test_get_host_raises_keyerror_if_unknown():
    e = Environment('name')
    with pytest.raises(KeyError):
        e.get_host('asdf')


def test_get_host_normalizes_hostname():
    e = Environment('name')
    e.hosts['asdf.example.com'] = host = Mock()
    e.host_domain = 'example.com'
    assert host == e.get_host('asdf')
    assert host == e.get_host('asdf.example.com')


def test_normalize_hostname_regression_11156():
    # The issue here was that we used "rstrip" which works on characters,
    # not substrings. Having the domain (example.com) start with an eee
    # causes the hostname to get stripped of it's "eee"s ending in an
    # empty hostname accidentally.
    e = Environment('name')
    e.hosts['eee.example.com'] = host = Mock()
    e.host_domain = 'example.com'
    assert host == e.get_host('eee')


def test_get_host_without_subdomain_also_works():
    e = Environment('name')
    e.hosts['example.com'] = host = Mock()
    e.host_domain = 'example.com'
    assert host == e.get_host('example.com')


def test_get_root_raises_keyerror_on_nonassigned_component():
    e = Environment('foo')
    with pytest.raises(KeyError):
        e.get_root('asdf', 'localhost')


def test_multiple_components(sample_service):
    e = Environment('test-multiple-components')
    e.load()
    components = dict(
        (host, list(sorted(c.name for c in e.root_dependencies(host=host))))
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


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_should_merge_single_and_multi_definition(add_root):
    e = Environment('name')
    config = Config(None)
    config.config.read_string("""
[hosts]
foo = bar
[host:baz]
components = bar
    """)
    e.load_hosts(config)
    assert [mock.call('bar', 'foo', [], False),
            mock.call('bar', 'baz', [], False)] == \
        add_root.call_args_list


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_should_load_single_hosts_section(add_root):
    e = Environment('name')
    config = Config(None)
    config.config.read_string("""
[hosts]
foo = bar
    """)
    e.load_hosts(config)
    add_root.assert_called_once_with('bar', 'foo', [], False)


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_should_load_multi_hosts_section(add_root):
    pass
    e = Environment('name')
    config = Config(None)
    config.config.read_string("""
[host:foo]
components = bar
    """)
    e.load_hosts(config)
    add_root.assert_called_once_with('bar', 'foo', [], False)


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_multi_should_use_ignore_flag(add_root):
    pass
    e = Environment('name')
    config = Config(None)
    config.config.read_string("""
[host:foo]
components = bar
ignore = True
    """)
    e.load_hosts(config)
    assert e.hosts['foo'].ignore


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_should_break_on_duplicate_definition(add_root):
    e = Environment('name')
    config = Config(None)
    config.config.read_string("""
[hosts]
foo = bar
[host:foo]
components = bar
    """)
    e.load_hosts(config)
    assert e.exceptions
    assert 'foo' == e.exceptions[0].hostname


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_multi_should_use_env_platform(add_root):
    e = Environment('name')
    e.platform = mock.sentinel.platform
    config = Config(None)
    config.config.read_string("""
[host:foo]
components = bar
ignore = True
    """)
    e.load_hosts(config)
    assert e.hosts['foo'].platform == mock.sentinel.platform


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_multi_should_use_host_platform_if_given(add_root):
    pass
    e = Environment('name')
    e.platform = mock.sentinel.platform
    config = Config(None)
    config.config.read_string("""
[host:foo]
components = bar
platform = specific
    """)
    e.load_hosts(config)
    assert e.hosts['foo'].platform == 'specific'


@mock.patch('batou.environment.Environment.add_root')
def test_load_hosts_single_should_use_env_platform(add_root):
    e = Environment('name')
    e.platform = mock.sentinel.platform
    config = Config(None)
    config.config.read_string("""
[hosts]
foo = bar
    """)
    e.load_hosts(config)
    assert e.hosts['foo'].platform == mock.sentinel.platform


def test_host_data_is_passed_to_host_object():
    e = Environment('name')
    config = Config(None)
    config.config.read_string("""
[host:foo]
components = bar
data-alias = baz
    """)
    e.load_hosts(config)
    assert 'baz' == e.hosts['foo'].data['alias']


def test_components_for_host_can_be_retrieved_from_environment(sample_service):
    e = Environment('test-overlapping-components')
    e.load()

    def _get_components(hostname):
        return sorted(e.components_for(host=e.hosts[hostname]).keys())

    assert ['hello1', 'hello2'] == _get_components('localhost')
    assert ['hello3'] == _get_components('other')
    assert ['hello2', 'hello3'] == _get_components('this')

    localhost = e.hosts['localhost']
    assert 'hello1' in localhost.components
    assert 'hello2' in localhost.components
    assert 'hello3' not in localhost.components


@mock.patch('batou.remote_core.Output.line')
def test_log_in_component_configure_is_put_out(
        output, sample_service):
    e = Environment('test-with-provide-require')
    e.load()
    e.configure()
    log = '\n'.join(c[0][0].strip() for c in output.call_args_list)
    # Provide is *always* logged first, due to provide/require ordering.
    assert """\
Provide
Pre sub
Sub!
Post sub""" == log

    output.reset_mock()
    for root in e.root_dependencies():
        root.component.deploy(True)

    log = '\n'.join(c[0][0].strip() for c in output.call_args_list)
    assert """\
localhost > Hello
localhost: <Hello (localhost) "Hello"> verify: asdf=None\
""" == log


def test_resolver_overrides(sample_service):
    e = Environment('test-resolver')
    e.load()
    assert {'localhost': '127.0.0.2'} == e._resolve_override
    assert {'localhost': '::2'} == e._resolve_v6_override

    assert '127.0.0.2' == batou.utils.resolve('localhost')
    assert '::2' == batou.utils.resolve_v6('localhost', 0)


def test_resolver_overrides_invalid_address(sample_service):
    e = Environment('test-resolver-invalid')
    e.load()

    with pytest.raises(batou.InvalidIPAddressError) as err:
        e.configure()
    assert "thisisinvalid" == err.value.address
