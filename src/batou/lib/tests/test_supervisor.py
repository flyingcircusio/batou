import batou.lib.supervisor
import os.path
import pytest


@pytest.yield_fixture
def supervisor(root, request):
    # Urks. Otherwise OS X ends up with socket paths that are too long.
    supervisor = batou.lib.supervisor.Supervisor(
        pidfile='supervisor.pid',
        socketpath='/tmp/batou-test-supervisor.sock')
    root.component += supervisor
    root.component.deploy()
    yield supervisor
    supervisor.cmd(
        '{}/bin/supervisorctl shutdown'.format(supervisor.workdir))


@pytest.mark.slow
def test_waits_for_start(root, supervisor):
    root.component += batou.lib.supervisor.Program(
        'foo', command_absolute=False,
        command='bash', args='-c "sleep 1; touch %s/foo; sleep 3600"' % (
            root.workdir), options=dict(startsecs=2))
    root.component.deploy()
    assert os.path.exists('%s/foo' % root.workdir)


@pytest.mark.slow
def test_does_not_start_disabled_program(root, supervisor):
    root.component += batou.lib.supervisor.Program(
        'foo', command_absolute=False,
        command='bash', args='-c "sleep 1; touch %s/foo; sleep 3600"' % (
            root.workdir), options=dict(startsecs=2), enable=False)
    root.component.deploy()
    assert not os.path.exists('%s/foo' % root.workdir)


@pytest.mark.slow
def test_program_does_not_start_within_startsecs_raises(root, supervisor):
    root.component += batou.lib.supervisor.Program(
        'foo', command_absolute=False, command='true',
        options=dict(startsecs=1))
    with pytest.raises(RuntimeError):
        root.component.deploy()


@pytest.mark.slow
def test_starts_stopped_program(root, supervisor):
    root.component += batou.lib.supervisor.Program(
        'foo', command_absolute=False,
        command='bash', args='-c "sleep 3600"', options=dict(startsecs=2))
    root.component.deploy()
    supervisor.cmd(
        '{}/bin/supervisorctl stop foo'.format(supervisor.workdir))
    root.component.deploy()
    assert 'RUNNING' in supervisor.cmd(
        '{}/bin/supervisorctl status foo'.format(supervisor.workdir))[0]


@pytest.mark.slow
def test_enable_false_reports_not_running_when_daemon_stopped(root):
    supervisor = batou.lib.supervisor.Supervisor(
        enable=False,
        pidfile='supervisor.pid',
        socketpath='/tmp/batou-test-supervisor.sock')
    root.component += supervisor
    # assert nothing raised
    root.component.deploy()


@pytest.mark.slow
def test_enable_true_reports_not_running_when_daemon_stopped(root, supervisor):
    supervisor.cmd(
        '{}/bin/supervisorctl shutdown'.format(supervisor.workdir))
    # assert nothing raised
    root.component.deploy()
