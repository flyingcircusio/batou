from batou import UpdateNeeded, output
from batou.component import Component, Attribute, handle_event
from batou.lib.buildout import Buildout
from batou.lib.file import File, Directory
from batou.lib.nagios import ServiceCheck
from batou.lib.logrotate import RotatedLogfile
from batou.lib.service import Service
from batou.utils import Address
import os
import os.path
import time


class Program(Component):

    program_section = """
[program:{{component.name}}]
command = {{component.command}} {{component.args}}
process_name = {{component.name}}
directory = {{component.directory}}
priority = {{component.priority}}
stderr_logfile = {{component.supervisor.logdir.path}}/{{component.name}}.log
stderr_logfile_backups = 0
stderr_logfile_maxbytes = 0
stdout_logfile = {{component.supervisor.logdir.path}}/{{component.name}}.log
stdout_logfile_backups = 0
stdout_logfile_maxbytes = 0
redirect_stderr = true
{% for k, v in component.options.items() %}
{{k}} = {{v}}
{% endfor -%}
"""

    namevar = 'name'

    # Can this be deployed while running or should the process be stopped
    # prior to deploying it?
    # hot = it can keep running
    # cold = needs to be stopped
    deployment = 'hot'

    command = None
    command_absolute = True
    options = {}
    args = ''
    priority = 10
    directory = None

    program_template = ('{priority} {name} ({options}) {command} '
                        '{args} {directory} true')

    def configure(self):
        self.supervisor = self.require_one('supervisor', self.host)
        if not self.command:
            raise ValueError(
                '`command` option missing for program {}'.format(self.name))
        if not self.directory:
            self.directory = self.workdir
        if self.command_absolute:
            self.command = os.path.normpath(
                os.path.join(self.workdir, self.command))

        if 'startsecs' not in self.options:
            self.options['startsecs'] = 5
        if 'startretries' not in self.options:
            self.options['startretries'] = 3
        self.supervisor.max_startup_delay = max(
            int(self.options['startsecs']), self.supervisor.max_startup_delay)

        self.config = self.expand(
            '{{component.supervisor.program_config_dir.path}}/'
            '{{component.name}}.conf')
        self += File(self.config,
                     content=self.expand(self.program_section))

    def ctl(self, args, **kw):
        command = '{}/bin/supervisorctl'.format(self.supervisor.workdir)
        return self.cmd('{} {}'.format(command, args), **kw)

    def verify(self):
        if not self.supervisor.enable:
            return
        self.parent.assert_no_subcomponent_changes()
        out, err = self.ctl('status {}'.format(self.name))
        if 'RUNNING' not in out:
            raise UpdateNeeded()

    def update(self):
        self.ctl('reread')
        self.ctl('update')
        self.ctl('restart {}'.format(self.name))
        if self.supervisor.wait_for_running:
            for retry in range(self.options['startsecs']):
                time.sleep(1)
                out, err = self.ctl('status {}'.format(self.name))
                if 'RUNNING' in out:
                    return
            raise RuntimeError(
                'Program "{}" did not start up'.format(self.name))

    # Keep track whether
    _evaded = False

    @handle_event('before-update', 'precursor')
    def evade(self, component):
        if self.deployment == 'hot':
            return
        if self._evaded:
            return
        # Only try once. Keep going anyway.
        self._evaded = True
        output.annotate(
            u"\u2623 Stopping {} for cold deployment".format(self.name))
        try:
            self.ctl('stop {}'.format(self.name))
        except Exception:
            pass


class Eventlistener(Program):

    program_section = """
[eventlistener:{{component.name}}]
command = {{component.command}} {{component.args}}
events = {{component.events}}
process_name={{component.name}}
"""

    namevar = 'name'

    events = ('TICK_60',)
    command = None
    args = None

    def configure(self):
        if not isinstance(self.events, str):
            self.events = ','.join(self.events)
            # Not sure what's right. We only use eventlisteners with superlance
            # which lives in the supervisor's workdir. However, the
            # EventListener component gets instanciated as a sub-component of
            # the actual component using it - which doesn't know about the path
            # to the superlance plugins. :/
            self.supervisor = self.require_one('supervisor', self.host)
            self.command = os.path.normpath(
                os.path.join(self.supervisor.workdir, self.command))

        super(Eventlistener, self).configure()


class Supervisor(Component):

    address = Attribute(Address, 'localhost:9001')
    buildout_cfg = os.path.join(
        os.path.dirname(__file__), 'resources', 'supervisor.buildout.cfg')
    supervisor_conf = os.path.join(
        os.path.dirname(__file__), 'resources', 'supervisor.conf')

    program_config_dir = None
    logdir = None
    loglevel = 'info'
    # Allows turning "everything off" via environment configuration
    enable = Attribute('literal', 'True')
    # Hot deployments: if supervisor is already running stuff - keep them
    # running
    # Cold deployments: if supervisor is already running: let it run
    # but shutdown all processes before continuing
    deployment_mode = Attribute(str, 'hot')
    max_startup_delay = Attribute(int, 0)
    wait_for_running = Attribute('literal', 'True')
    pidfile = Attribute(str, '/run/local/supervisord.pid', map=True)
    socketpath = Attribute(
        str, '{{component.workdir}}/supervisor.sock', map=True)

    def configure(self):
        self.provide('supervisor', self)

        buildout_cfg = File('buildout.cfg',
                            source=self.buildout_cfg)
        self += Buildout('buildout',
                         version='2.4.3',
                         setuptools='18.3.1',
                         config=buildout_cfg,
                         python='2.7')

        self.program_config_dir = Directory('etc/supervisor.d', leading=True)
        self += self.program_config_dir
        self += File('etc/supervisord.conf',
                     source=self.supervisor_conf)
        self.logdir = Directory('var/log', leading=True)
        self += self.logdir

        postrotate = self.expand(
            'kill -USR2 $({{component.workdir}}/bin/supervisorctl pid)')
        self += RotatedLogfile('var/log/*.log', postrotate=postrotate)

        self += Service('bin/supervisord', pidfile=self.pidfile)

        if self.enable:
            self += RunningSupervisor()
        else:
            self += StoppedSupervisor()

        # Nagios check
        self += File('check_supervisor',
                     mode=0o755,
                     source=os.path.join(
                         os.path.dirname(__file__),
                         'resources',
                         'check_supervisor.py.in'))

        self += ServiceCheck(
            'Supervisor programs',
            nrpe=True,
            command=self.expand('{{component.workdir}}/check_supervisor'))


class RunningSupervisor(Component):

    action = None
    reload_timeout = 60

    def verify(self):
        self.assert_file_is_current(
            self.parent.pidfile, ['bin/supervisord', 'etc/supervisord.conf'])
        if not self.is_running():
            raise UpdateNeeded()

    def is_running(self):
        pid, err = self.cmd('bin/supervisorctl pid')
        try:
            int(pid) > 0
        except ValueError:
            return False
        return True

    def update(self):
        if not self.is_running():
            self.cmd('bin/supervisord')
        else:
            self.reload_supervisor()
        if self.parent.wait_for_running:
            # Wait max startup time now that supervisor is back
            time.sleep(self.parent.max_startup_delay)

    def reload_supervisor(self):
        self.cmd('bin/supervisorctl reload')
        # Reload is asynchronous and doesn't wait for supervisor to become
        # fully running again. We actually could monitor supervisorctl,
        # though. This can take a long time if supervisor needs to orderly
        # shut down a lot of services.
        wait = self.reload_timeout
        while wait:
            out, err = '', ''
            # Supervisor tends to "randomly" set zero and non-zero exit codes.
            # See https://github.com/Supervisor/supervisor/issues/24 :-/
            out, err = self.cmd('bin/supervisorctl pid',
                                ignore_returncode=True)
            if 'SHUTDOWN_STATE' in out:
                time.sleep(1)
                continue
            try:
                int(out) > 0
            except ValueError:
                time.sleep(1)
                wait -= 1
            else:
                break
        else:
            raise RuntimeError(
                'supervisor master process did not start within {} seconds'
                .format(self.reload_timeout))


class StoppedSupervisor(Component):

    def verify(self):
        out, err = self.cmd('bin/supervisorctl pid')
        try:
            int(out)
        except ValueError:
            return
        raise UpdateNeeded()

    def update(self):
        self.cmd('bin/supervisorctl shutdown')
