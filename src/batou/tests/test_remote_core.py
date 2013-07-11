from batou import remote_core
import inspect
import mock
import os.path
import pytest


def test_host_and_channel_exist():
    assert remote_core.channel is None
    assert remote_core.host is None


def test_lock():
    remote_core.lock()


def test_cmd():
    result = remote_core.cmd('echo "asdf"')
    assert result == "asdf\n"


@pytest.fixture
def mock_remote_core(monkeypatch):
    # Suppress active actions in the remote_core module
    monkeypatch.setattr(remote_core, 'cmd', mock.Mock())
    monkeypatch.setattr(remote_core, 'get_deployment_base', mock.Mock())


def test_update_code_existing_target(mock_remote_core, tmpdir):
    remote_core.get_deployment_base.return_value = str(tmpdir)
    remote_core.update_code('http://bitbucket.org/gocept/batou')
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert calls.next() == 'hg pull http://bitbucket.org/gocept/batou'
    assert calls.next() == 'hg up -C'
    assert calls.next() == 'hg id -i'


def test_update_code_new_target(mock_remote_core, tmpdir):
    remote_core.get_deployment_base.return_value = str(tmpdir / 'foo')
    remote_core.update_code('http://bitbucket.org/gocept/batou')
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert calls.next() == 'hg init {}'.format(
        remote_core.get_deployment_base())
    assert calls.next() == 'hg pull http://bitbucket.org/gocept/batou'
    assert calls.next() == 'hg up -C'
    assert calls.next() == 'hg id -i'


def test_expand_deployment_base():
    assert (remote_core.get_deployment_base() ==
            os.path.expanduser('~/deployment'))


def test_deploy_component(monkeypatch):
    monkeypatch.setattr(remote_core, 'host', dict(foo=mock.Mock()))
    remote_core.deploy_component('foo')
    assert remote_core.host['foo'].deploy.call_count == 1


class DummyChannel(object):

    _closed = False

    def __init__(self):
        self.receivequeue = []
        self.sendqueue = []

    def isclosed(self):
        return self._closed

    def receive(self, timeout=None):
        result = self.receivequeue.pop()
        if not self.receivequeue:
            self._closed = True
        return result

    def send(self, item):
        self.sendqueue.append(item)


@pytest.fixture
def remote_core_mod():
    channel = DummyChannel()

    local_namespace = dict(channel=channel, __name__='__channelexec__')

    remote_core_mod = compile(
        inspect.getsource(remote_core),
        inspect.getsourcefile(remote_core),
        'exec')

    def run():
        exec remote_core_mod in local_namespace

    return (channel, run)


def test_channelexec_already_closed(remote_core_mod):
    channel, run = remote_core_mod
    channel._closed = True
    run()
    assert channel.receivequeue == []
    assert channel.sendqueue == []


def test_channelexec_echo_cmd(remote_core_mod):
    channel, run = remote_core_mod
    channel.receivequeue.append(('cmd', ('echo "asdf"',), {}))
    run()
    assert channel.isclosed()
    assert channel.receivequeue == []
    assert channel.sendqueue == ['asdf\n']


def test_channelexec_handle_exception(remote_core_mod):
    channel, run = remote_core_mod
    channel.receivequeue.append(('cmd', ('fdjkahfkjdasbfda',), {}))
    run()
    assert channel.isclosed()
    assert channel.receivequeue == []
    assert channel.sendqueue == [(
        'batou-remote-core-error',
        'CalledProcessError',
        'subprocess',
        ())]
