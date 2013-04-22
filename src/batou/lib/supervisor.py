from batou import UpdateNeeded
from batou.component import Component, HookComponent
from batou.lib.buildout import Buildout
from batou.lib.file import File, Directory
from batou.lib.nagios import ServiceCheck
from batou.lib.logrotate import RotatedLogfile
from batou.lib.service import Service
from batou.utils import Address
import ast
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
{% for k, v in component.options.items() %}
{{k}} = {{v}}
{% endfor %}
redirect_stderr = true
"""

    namevar = 'name'

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
            raise ValueError('`command` option missing for program {}'.
                format(self.name))
        if not self.directory:
            self.directory = self.workdir
        if self.command_absolute:
            self.command = os.path.normpath(
               os.path.join(self.workdir, self.command))

        if not 'startsecs' in self.options:
            self.options['startsecs'] = 5
        self.supervisor.max_startup_delay = max(
            int(self.options['startsecs']), self.supervisor.max_startup_delay)

        self.config = self.expand(
            '{{component.supervisor.program_config_dir.path}}/'
            '{{component.name}}.conf')
        self += File(self.config,
                     content=self.expand(self.program_section))

    def ctl(self, args):
        command = '{}/bin/supervisorctl'.format(self.supervisor.workdir)
        return self.cmd('{} {}'.format(command, args))

    def verify(self):
        self.parent.assert_no_subcomponent_changes()
        out, err = self.ctl('status {}'.format(self.name))
        if not 'RUNNING' in out:
            raise UpdateNeeded()

    def update(self):
        self.ctl('reread')
        self.ctl('restart {}'.format(self.name))


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

    address = 'localhost:9001'
    buildout_cfg = os.path.join(os.path.dirname(__file__), 'resources',
                             'supervisor.buildout.cfg')
    supervisor_conf = os.path.join(os.path.dirname(__file__), 'resources',
                             'supervisor.conf')

    program_config_dir = None
    logdir = None
    loglevel = 'info'
    enable = 'True'  # Allows turning "everything off" via environment configuration
    max_startup_delay = 0

    def configure(self):
        self.address = Address(self.address)
        self.provide('supervisor', self)

        buildout_cfg = File('buildout.cfg',
                            source=self.buildout_cfg)
        self += Buildout('buildout',
            config=buildout_cfg,
            python='2.7')

        self.program_config_dir = Directory('etc/supervisor.d', leading=True)
        self += self.program_config_dir
        self += File('etc/supervisord.conf',
                     source=self.supervisor_conf,
                     is_template=True)
        self.logdir = Directory('var/log', leading=True)
        self += self.logdir

        postrotate = self.expand('kill -USR2 $({{component.workdir}}/bin/supervisorctl pid)')
        self += RotatedLogfile('var/log/*.log', postrotate=postrotate)

        self += Service('bin/supervisord', pidfile='var/supervisord.pid')

        self.enable = ast.literal_eval(self.enable)
        if self.enable:
            self += RunningSupervisor()
        else:
            self += StoppedSupervisor()

        # Nagios check
        self += File('check_supervisor',
                mode=0o755,
                source=os.path.join(
                    os.path.dirname(__file__), 'resources',
                    'check_supervisor.py.in'),
                is_template=True)

        self += ServiceCheck('Supervisor programs',
            nrpe=True,
            command=self.expand('{{component.workdir}}/check_supervisor'))


class RunningSupervisor(Component):

    action = None
    reload_timeout = 60

    def verify(self):
        self.assert_file_is_current(
            'var/supervisord.pid',
            ['bin/supervisord', 'etc/supervisord.conf'])

    def update(self):
        out, err = self.cmd('bin/supervisorctl pid')
        try:
            int(out)
        except ValueError:
            self.cmd('bin/supervisord')
        else:
            self.cmd('bin/supervisorctl reload')
            # Reload is asynchronous and doesn't wait for supervisor to become
            # fully running again. We actually could monitor supervisorctl,
            # though. This can take a long time if supervisor needs to orderly
            # shut down a lot of services.
            wait = self.reload_timeout
            while wait:
                wait -= 1
                try:
                    out, err = '', ''
                    out, err = self.cmd('bin/supervisorctl pid', silent=True)
                except RuntimeError, e:
                    # Supervisor tends to "randomly" set zero and non-zero exit
                    # codes. :/
                    # See https://github.com/Supervisor/supervisor/issues/24
                    pass

                if 'SHUTDOWN_STATE' in out:
                    wait += 1
                else:
                    try:
                        int(out)
                    except ValueError:
                        pass
                    else:
                        break
                time.sleep(1)
            else:
                raise RuntimeError(
                    'supervisor master process did not start within {} seconds'
                    .format(self.reload_timeout))
        # Wait max startup time now that supervisor is back
        time.sleep(self.parent.max_startup_delay)


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
