from batou.component import Component
from batou.lib import file
from batou import UpdateNeeded
import os.path


class Bootstrap(Component):

    python = None
    buildout = 'bin/buildout'
    bootstrap = os.path.join(os.path.dirname(__file__), 'resources',
                             'bootstrap.py')

    def configure(self):
        self += file.Content('bootstrap.py', source=self.bootstrap)

    def verify(self):
        self.assert_file_is_current(
            self.buildout, ['bootstrap.py', self.python])
        buildout = open('bin/buildout', 'r').readlines()[0]
        if not buildout.startswith(
                '#!{0}/{1}'.format(self.root.compdir, self.python)):
            raise UpdateNeeded()

    def update(self):
        self.cmd('%s bootstrap.py' % self.python)


class Buildout(Component):

    timeout = 3
    extends = ()    # Extends need to be aspects that have a path
    python = None

    def configure(self):
        self += file.Content('buildout.cfg')
        self += Bootstrap(python=self.python)
        # Maybe allow SourceDir to be given as a parameter.
        # self += SourceDir('profiles')

    def verify(self):
        self.assert_file_is_current(
            '.installed.cfg', ['bin/buildout', 'buildout.cfg'])
        self.assert_file_is_current(
            '.batou.buildout.success', ['.installed.cfg'])

    def update(self):
        self.cmd('bin/buildout -t {}'.format(self.timeout))
        self.touch('.batou.buildout.success')
