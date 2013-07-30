from batou.environment import Environment
from mock import Mock
import pytest


def test_environment_should_raise_if_no_config_file(tmpdir):
    e = Environment(u'foobar')
    with pytest.raises(ValueError):
        e.load()


def test_configure_should_use_defaults(sample_service):
    e = Environment(u'test-without-env-config')
    e.load()
    assert None == e.host_domain
    assert 'default' == e.branch


def test_configure_should_use_config(sample_service):
    e = Environment(u'test-with-env-config')
    e.load()
    assert e.service_user == u'joe'
    assert e.host_domain == u'example.com'
    assert e.branch == u'release'


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
