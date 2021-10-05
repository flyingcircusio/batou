import mock
import pytest

from ..host import RPCWrapper


def test_rpcwrapper_returns_result():
    host = mock.Mock()
    host.channel.receive.return_value = ("batou-result", mock.sentinel.result)
    rpc = RPCWrapper(host)
    assert mock.sentinel.result == rpc.foo()


def test_rpcwrapper_error_contains_hostname():
    host = mock.Mock()
    host.fqdn = "foo.example.com"
    host.channel.receive.return_value = ("batou-error", None)
    rpc = RPCWrapper(host)
    with pytest.raises(RuntimeError) as e:
        rpc.foo()
    assert ("foo.example.com: Remote exception encountered.", ) == e.value.args
