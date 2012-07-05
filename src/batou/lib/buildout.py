from batou.component import Component
from batou.lib.python import VirtualEnv
from batou.lib.file import File
from batou import UpdateNeeded
import os.path


class Bootstrap(Component):

    python = None
    buildout = 'bin/buildout'
    bootstrap = os.path.join(os.path.dirname(__file__), 'resources',
                             'bootstrap.py')

    def configure(self):
        self += File('bootstrap.py', source=self.bootstrap)

    def verify(self):
        self.assert_file_is_current(
            self.buildout, ['bootstrap.py', self.python])
        buildout = open('bin/buildout', 'r').readlines()[0]
        if not buildout.startswith(
                '#!{0}/{1}'.format(self.root.workdir, self.python)):
            raise UpdateNeeded()

    def update(self):
        self.cmd('%s bootstrap.py' % self.python)


class Buildout(Component):

    timeout = 3
    extends = ()    # Extends need to be aspects that have a path
    config = None

    def configure(self):
        if self.config is None:
            self.config = File('buildout.cfg',
                               source='buildout.cfg',
                               is_template=True)
        if isinstance(self.config, Component):
            self.config = [self.config]
        for component in self.config:
            self += component
        venv = VirtualEnv(self.python)
        self += venv
        self += Bootstrap(python=venv.python)

    def verify(self):
        config_paths = [x.path for x in self.config]
        self.assert_file_is_current(
            '.installed.cfg', ['bin/buildout'] + config_paths)
        self.assert_file_is_current(
            '.batou.buildout.success', ['.installed.cfg'])

    def update(self):
        self.cmd('bin/buildout -t {}'.format(self.timeout))
        self.touch('.batou.buildout.success')
