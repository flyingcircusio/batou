from ..host import Host
import mock
import pytest


@pytest.fixture
def host():
    return Host('foo.testing', mock.sentinel.env)


def test_data_can_set_and_get(host):
    # Okay, this test is almost too silly to have it here.
    host.data['foo'] = 'bar'
    assert 'bar' == host.data['foo']
