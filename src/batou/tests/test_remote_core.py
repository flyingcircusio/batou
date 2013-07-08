from batou import remote_core
import inspect
import mock


def test_host_and_channel_exist():
    assert remote_core.channel is None
    assert remote_core.host is None


def test_lock():
    remote_core.lock()


def test_cmd():
    result = remote_core.cmd('echo "asdf"')
    assert result == "asdf\n"


def test_channelexec():
    # Simulate the channel exec call
    channel = mock.Mock()
    source = inspect.getsource(remote_core)

    local_namespace = dict(channel=channel, __name__='__channelexec__')
    exec source in local_namespace
    assert {} == local_namespace
