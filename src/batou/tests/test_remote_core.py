from batou import remote_core
import inspect
import mock
import os.path
import pytest


def test_deployment_and_channel_exist_as_names():
    assert remote_core.channel is None
    assert remote_core.deployment is None


def test_lock():
    remote_core.lock()


def test_cmd():
    result = remote_core.cmd('echo "asdf"')
    assert result == "asdf\n"


@pytest.fixture
def mock_remote_core(monkeypatch, tmpdir):
    # Suppress active actions in the remote_core module
    monkeypatch.setattr(remote_core, 'cmd', mock.Mock())
    monkeypatch.setattr(remote_core, 'target_directory', mock.Mock())
    remote_core.target_directory.return_value = str(tmpdir)


def test_update_code_existing_target(mock_remote_core):
    remote_core.update_code('http://bitbucket.org/gocept/batou')
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert calls.next() == 'hg pull http://bitbucket.org/gocept/batou'
    assert calls.next() == 'hg up -C'
    assert calls.next() == 'hg id -i'


def test_update_code_new_target(mock_remote_core):
    remote_core.target_directory.return_value += '/foo'

    remote_core.update_code('http://bitbucket.org/gocept/batou')
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert remote_core.cmd.call_count == 4
    assert calls.next() == 'hg init {}'.format(
        remote_core.target_directory())
    assert calls.next() == 'hg pull http://bitbucket.org/gocept/batou'
    assert calls.next() == 'hg up -C'
    assert calls.next() == 'hg id -i'


def test_build_batou_fresh_install(mock_remote_core):
    remote_core.build_batou('.', '0.9', '2.0')
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert remote_core.cmd.call_count == 4
    assert calls.next() == 'virtualenv --no-site-packages --python python2.7 .'
    assert calls.next() == 'bin/pip install --force-reinstall setuptools==0.9'
    assert calls.next() == 'bin/pip install --force-reinstall zc.buildout==2.0'
    assert calls.next() == 'bin/buildout -t 15'


def test_build_batou_virtualenv_exists(mock_remote_core):
    os.mkdir(remote_core.target_directory() + '/bin')
    open(remote_core.target_directory() + '/bin/python2.7', 'w')
    remote_core.build_batou('.', '0.9', '2.0')
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert remote_core.cmd.call_count == 3
    assert calls.next() == 'bin/pip install --force-reinstall setuptools==0.9'
    assert calls.next() == 'bin/pip install --force-reinstall zc.buildout==2.0'
    assert calls.next() == 'bin/buildout -t 15'


def test_expand_deployment_base():
    assert (remote_core.target_directory() ==
            os.path.expanduser('~/deployment'))


def test_deploy_component(monkeypatch):
    monkeypatch.setattr(remote_core, 'deployment', mock.Mock())
    remote_core.deploy('foo')
    assert remote_core.deployment.deploy.call_count == 1


class DummyChannel(object):

    _closed = False

    def __init__(self):
        self.receivequeue = []
        self.sendqueue = []

    def isclosed(self):
        return self._closed

    def receive(self, timeout=None):
        result = self.receivequeue.pop(0)
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


def test_channelexec_multiple_echo_cmds(remote_core_mod):
    channel, run = remote_core_mod
    channel.receivequeue.append(('cmd', ('echo "asdf1"',), {}))
    channel.receivequeue.append(('cmd', ('echo "asdf2"',), {}))
    run()
    assert channel.isclosed()
    assert channel.receivequeue == []
    assert channel.sendqueue == ['asdf1\n', 'asdf2\n']


def test_channelexec_handle_exception(remote_core_mod):
    channel, run = remote_core_mod
    channel.receivequeue.append(('cmd', ('fdjkahfkjdasbfda',), {}))
    run()
    assert channel.isclosed()
    assert channel.receivequeue == []
    response = channel.sendqueue[0]
    assert response[0] == 'batou-remote-core-error'
    assert ('CalledProcessError: Command \'[\'fdjkahfkjdasbfda\']\' returned '
            'non-zero exit status 127' in response[1])
