from batou.component import Component, HookComponent
from batou.lib.buildout import Buildout
from batou.lib.file import File, Directory
from batou.lib.nagios import Check
from batou.lib.service import Service
from batou.utils import Address
import os
import os.path


class Program(HookComponent):
    """ XXX
            * priority (integer)
            * process_name (string)
            * options (dictionary)
            * command (string)
            * arguments (String)
            * restart - if True, restart this daemon during the current batou
              run.
    """

    namevar = 'name'
    key = 'batou.lib.supervisor:Program'

    command = None
    options = {}
    args = ''
    priority = 10

    restart = False  # ... if parent component changed

    program_template = ('{priority} {name} ({options}) {command} '
                        '{args} {workdir} true')

    def configure(self):
        super(Program, self).configure()
        self.command = os.path.normpath(
           os.path.join(self.workdir, self.command))

    def format(self, supervisor):
        if not 'startsecs' in self.options:
            self.options['startsecs'] = 10
        # XXX some of those could be extracted as platform-specific components
        self.options['stdout_logfile'] = '%s/var/log/%s.log' % (
            supervisor.workdir, self.name)
        self.options['stdout_logfile_maxbytes'] = 0
        self.options['stdout_logfile_backups'] = 0
        self.options['stderr_logfile'] = '%s/var/log/%s.log' % (
            supervisor.workdir, self.name)
        self.options['stderr_logfile_maxbytes'] = 0
        self.options['stderr_logfile_backups'] = 0
        options = '{}'.format(' '.join(
            '%s=%s' % (k, v) for k, v in sorted(self.options.items())))
        args = '[{}]'.format(self.args)
        return self.program_template.format(
                priority=self.priority,
                name=self.name,
                options=options,
                command=self.command,
                workdir=self.workdir,
                args=args)


class Eventlistener(HookComponent):
    """ XXX
        * *:eventlistener - supervisor event listener
            * name
            * events - list of supervisord events
            * command
            * args

            `events` defaults to TICK_60
    """

    namevar = 'name'
    key = 'batou.lib.supervisor:Eventlistener'

    events = ('TICK_60',)
    command = None
    args = None

    def configure(self):
        super(Eventlistener, self).configure()
        self.events = ' '.join(self.events)

    def format(self, supervisor):
        return self.expand('{{component.name}} {{component.events}} '
                           '{{component.command}} [{{component.args}}]')


class Supervisor(Component):
    """Start other components' daemons.

    This component runs supervisord and provides hooks for other components to
    register their daemons.

    Configuration::

        [component:supervisord]
        address = INET address that supervisor should listen on

    Imported hooks:

        * batou.lib.supervisor:Program - other components' daemon definitions

            See the `Program` component.

        * batou.lib.supervisor:Eventlistener - other components' eventlistener
           definitions

            See the `Eventlistener` component.

    """

    address = 'localhost:9001'
    buildout_cfg = os.path.join(os.path.dirname(__file__), 'resources',
                             'supervisor.buildout.cfg')

    def configure(self):
        self.address = Address(self.address)
        self.programs = self.require(Program.key, self.host)
        self.eventlisteners = self.require(
            Eventlistener.key, self.host, strict=False)

        buildout_cfg = File('buildout.cfg',
            source=self.buildout_cfg,
            template_context=self,
            is_template=True)

        self += Buildout('buildout',
            config=buildout_cfg,
            python='2.7')

        self += Check('Supervisor programs',
            host=self.host,
            command='check_supervisor')

        self += Directory('var/log', leading=True)

        self += Service('bin/supervisord', pidfile='var/supervisord.pid')

    def verify(self):
        self.assert_file_is_current(
            'var/supervisord.pid',
            ['.batou.buildout.success'])
        # XXX make assertions on files of programs?
        depending_components = self.programs + self.eventlisteners
        for component in depending_components:
            component.parent.assert_no_changes()

    def update(self):
        out, err = self.cmd('bin/supervisorctl pid')
        try:
            int(out)
        except ValueError:
            self.cmd('bin/supervisord')
        else:
            self.cmd('bin/supervisorctl reload')
        # XXX re-build selective restart

    def install_checks(self):
        # XXX transform to 0.2 version
        self.template('check_supervisor.py.in', 'check_supervisor')
        os.chmod('check_supervisor', 0o755)
        # relax permissions to allow nagios to execute the check
        self.cmd('chmod -R a+rX "%s/eggs" "%s"' % (
            self.service.base, self.compdir))
