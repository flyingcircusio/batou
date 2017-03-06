from ..host import Host
import mock
import pytest


@pytest.fixture
def host():
    return Host('foo.testing', mock.sentinel.env)


def test_data_can_set_and_get(host):
    host.data('foo', 'bar')
    assert 'bar' == host.data('foo')


def test_non_existing_key_returns_None(host):
    assert host.data('foo') is None
