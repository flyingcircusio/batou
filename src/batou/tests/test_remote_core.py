from batou import remote_core
import inspect
import mock
import os.path
import pytest


@pytest.yield_fixture(autouse=True)
def reset_global_vars():
    yield
    remote_core.target_directory = None
    remote_core.environment = None
    remote_core.deployment = None
    remote_core.channel = None


def test_deployment_and_channel_exist_as_names():
    assert remote_core.channel is None
    assert remote_core.deployment is None


def test_lock():
    remote_core.lock()


def test_cmd():
    result = remote_core.cmd('echo "asdf"')
    assert result == (b'asdf\n', b'')


@pytest.fixture
def mock_remote_core(monkeypatch):
    # Suppress active actions in the remote_core module
    monkeypatch.setattr(remote_core, 'cmd', mock.Mock())


def test_update_code_existing_target(mock_remote_core, tmpdir):
    remote_core.cmd.side_effect = [
        ('', ''),
        ('', ''),
        ('', ''),
        ('', '')]

    remote_core.ensure_repository(str(tmpdir), 'hg-pull')
    remote_core.hg_pull_code('http://bitbucket.org/flyingcircus/batou')
    remote_core.hg_update_working_copy('default')

    calls = iter(x[1][0] for x in remote_core.cmd.mock_calls)
    assert next(calls).startswith('hg init /')
    assert next(calls) == 'hg pull http://bitbucket.org/flyingcircus/batou'
    assert next(calls) == 'hg up -C default'
    assert next(calls) == 'hg id -i'
    assert remote_core.cmd.call_count == 4


def test_update_code_new_target(mock_remote_core, tmpdir):
    remote_core.cmd.side_effect = [
        ('', ''),
        ('', ''),
        ('', ''),
        ('', '')]
    remote_core.ensure_repository(str(tmpdir) + '/foo', 'hg-bundle')
    remote_core.hg_pull_code('http://bitbucket.org/flyingcircus/batou')
    remote_core.hg_update_working_copy('default')

    assert remote_core.cmd.call_count == 4
    calls = iter(x[1][0] for x in remote_core.cmd.mock_calls)
    assert next(calls) == 'hg init {}'.format(remote_core.target_directory)
    assert next(calls) == 'hg pull http://bitbucket.org/flyingcircus/batou'
    assert next(calls) == 'hg up -C default'
    assert next(calls) == 'hg id -i'


def test_hg_bundle_shipping(mock_remote_core, tmpdir):
    remote_core.ensure_repository(str(tmpdir) + '/foo', 'hg-bundle')
    remote_core.cmd.side_effect = [
        ("41fea38ce5d3", None),
        ("""\
changeset: 371:revision-a
summary:fdsa

changeset: 372:revision-b
""", None),
        ('', ''),
        ('', ''),
        ('', '')]
    heads = remote_core.hg_current_heads()
    assert heads == ['revision-a', 'revision-b']
    remote_core.hg_unbundle_code()
    remote_core.hg_update_working_copy('default')

    assert remote_core.cmd.call_count == 6
    calls = iter(x[1][0] for x in remote_core.cmd.mock_calls)
    assert next(calls) == 'hg init {}'.format(remote_core.target_directory)
    assert next(calls) == 'hg id -i'
    assert next(calls) == 'hg heads'
    assert next(calls) == 'hg -y unbundle batou-bundle.hg'
    assert next(calls) == 'hg up -C default'
    assert next(calls) == 'hg id -i'


def test_build_batou_fresh_install(mock_remote_core, tmpdir):
    remote_core.ensure_repository(str(tmpdir), 'hg-pull')
    remote_core.ensure_base('asdf')
    remote_core.cmd.reset_mock()
    remote_core.build_batou()
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert remote_core.cmd.call_count == 1
    assert next(calls) == './batou --help'


def test_build_batou_virtualenv_exists(mock_remote_core, tmpdir):
    remote_core.ensure_repository(str(tmpdir), 'hg-pull')
    remote_core.ensure_base('asdf')
    os.mkdir(remote_core.target_directory + '/bin')
    open(remote_core.target_directory + '/bin/python3', 'w')
    remote_core.build_batou()
    calls = iter([x[1][0] for x in remote_core.cmd.mock_calls])
    assert remote_core.cmd.call_count == 2
    next(calls)  # skip ensure_repository
    assert next(calls) == './batou --help'


def test_expand_deployment_base(tmpdir):
    with mock.patch('os.path.expanduser') as expanduser:
        expanduser.return_value = str(tmpdir)
        remote_core.ensure_repository('~/deployment', 'rsync')
    assert (remote_core.target_directory == str(tmpdir))


def test_deploy_component(monkeypatch):
    import batou
    monkeypatch.setattr(remote_core, 'deployment', mock.Mock())
    monkeypatch.setattr(batou, 'output', mock.Mock())
    remote_core.deploy('foo')
    assert remote_core.deployment.deploy.call_count == 1


def test_whoami():
    # Smoke test
    assert remote_core.whoami() != ''


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
        exec(remote_core_mod, local_namespace)

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
    assert channel.sendqueue == [('batou-result', (b'asdf\n', b''))]


def test_channelexec_multiple_echo_cmds(remote_core_mod):
    channel, run = remote_core_mod
    channel.receivequeue.append(('cmd', ('echo "asdf1"',), {}))
    channel.receivequeue.append(('cmd', ('echo "asdf2"',), {}))
    run()
    assert channel.isclosed()
    assert channel.receivequeue == []
    assert channel.sendqueue == [('batou-result', (b'asdf1\n', b'')),
                                 ('batou-result', (b'asdf2\n', b''))]


def test_channelexec_handle_exception(remote_core_mod):
    channel, run = remote_core_mod
    channel.receivequeue.append(('cmd', ('fdjkahfkjdasbfda',), {}))
    run()
    assert channel.isclosed()
    assert channel.receivequeue == []
    response = iter(channel.sendqueue)

    assert next(response) == (
        'batou-output', 'line', ('ERROR: fdjkahfkjdasbfda',),
        {'bold': True, 'red': True})

    assert next(response) == (
        'batou-output', 'line', ('Return code: 127',), {'red': True})

    assert next(response) == (
        'batou-output', 'line', ('STDOUT',), {'red': True})

    assert next(response) == ('batou-output', 'line', ('',), {})

    assert next(response) == (
        'batou-output', 'line', ('STDERR',), {'red': True})

    # Different /bin/sh versions have different error reporting
    assert next(response) in [
        ('batou-output', 'line',
            ('/bin/sh: fdjkahfkjdasbfda: command not found\n',), {}),
        ('batou-output', 'line',
            ('/bin/sh: 1: fdjkahfkjdasbfda: not found\n',), {})]

    assert next(response) == ('batou-error', None)

    with pytest.raises(StopIteration):
        next(response)


def test_git_remote_init_bundle(tmpdir):
    source = tmpdir.mkdir('source')
    dest = tmpdir.mkdir('dest')
    with source.as_cwd():
        remote_core.cmd('git init')
        source.join('foo.txt').write('bar')
        remote_core.cmd('git add foo.txt')
        remote_core.cmd('git commit -m bar')
        remote_core.cmd('git bundle create {} master '.format(
            dest.join('batou-bundle.git')))

    remote_core.ensure_repository(str(dest), 'git-bundle')
    remote_core.git_unbundle_code()
    remote_core.git_update_working_copy('master')

    assert 'bar' == dest.join('foo.txt').read()


def test_git_remote_init_pull(tmpdir):
    source = tmpdir.mkdir('source')
    dest = tmpdir.mkdir('dest')
    with source.as_cwd():
        remote_core.cmd('git init')
        source.join('foo.txt').write('bar')
        remote_core.cmd('git add foo.txt')
        remote_core.cmd('git commit -m bar')

        remote_core.ensure_repository(str(dest), 'git-bundle')
        remote_core.git_pull_code(str(source), 'master')
        remote_core.git_update_working_copy('master')

    assert 'bar' == dest.join('foo.txt').read()
