from batou import UpdateNeeded
from batou.component import Component
from batou.lib.file import File
from batou.lib.python import VirtualEnv
import contextlib
import os.path


class Bootstrap(Component):

    python = None
    buildout = 'bin/buildout'
    custom_bootstrap = False
    bootstrap = os.path.join(os.path.dirname(__file__), 'resources',
                             'bootstrap.py')
    config_file_name = 'buildout.cfg'

    def configure(self):
        if not self.custom_bootstrap:
            self += File('bootstrap.py', source=self.bootstrap)

    def verify(self):
        self.assert_file_is_current(
            self.buildout, ['bootstrap.py', self.python])
        buildout = open('bin/buildout', 'r').readlines()[0]
        if not buildout.startswith(
                '#!{0}/{1}'.format(self.root.workdir, self.python)):
            raise UpdateNeeded()

    def update(self):
        self.cmd('%s bootstrap.py --distribute' % self.python)


class Buildout(Component):

    timeout = 3
    extends = ()   # Extends need to be aspects that have a path
    use_default = True
    config = None
    additional_config = ()
    custom_bootstrap = False
    config_file_name = 'buildout.cfg'

    build_env = {}  # XXX not frozen. :/

    def configure(self):
        if not self.config and self.use_default:
            self.config = File('buildout.cfg',
                               source='buildout.cfg',
                               template_context=self.parent,
                               is_template=True)
        if isinstance(self.config, File):
            self.config_file_name = self.config.path
        if isinstance(self.config, Component):
            self.config = [self.config]
        if not self.config:
            self.config = []
        self.config.extend(self.additional_config)
        for component in self.config:
            self += component
        venv = VirtualEnv(self.python)
        self += venv
        self += Bootstrap(python=venv.python,
                          custom_bootstrap=self.custom_bootstrap,
                          config_file_name=self.config_file_name)

    def verify(self):
        # XXX we can't be sure that all config objects are files!
        self.assert_component_is_current(
            File('.installed.cfg'), [File('bin/buildout')] + self.config)
        self.assert_file_is_current(
            '.batou.buildout.success', ['.installed.cfg'])

    def update(self):
        with safe_environment(self.build_env):
            self.cmd('bin/buildout -t {} -c "{}" bootstrap'.format(
                self.timeout, self.config_file_name))
            self.cmd('bin/buildout -t {} -c "{}"'.format(
                self.timeout, self.config_file_name))
            self.touch('.batou.buildout.success')


@contextlib.contextmanager
def safe_environment(environment):
    old_env = os.environ.copy()
    for key, value in environment.items():
        old_env.setdefault(key, '')
        environment[key] = value.format(**old_env)
    try:
        os.environ.update(environment)
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)
