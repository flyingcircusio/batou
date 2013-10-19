from batou import UpdateNeeded
from batou.component import Component
from batou.lib.file import Directory
import os.path


class Checkout(Component):

    namevar = 'url'
    target = '.'
    revision = None

    def configure(self):
        self += Directory(self.target)

    def verify(self):
        with self.chdir(self.target):
            if not os.path.exists('.svn'):
                raise UpdateNeeded()
            stdout, stderr = self.cmd('svn info | grep Revision:')
            current_revision = stdout.replace('Revision:', '').strip()
            if current_revision != self.revision:
                raise UpdateNeeded()

    def update(self):
        with self.chdir(self.target):
            if not os.path.exists('.svn'):
                self.cmd(self.expand(
                    'svn co {{component.url}} . -r {{component.revision}}'))
            else:
                self.cmd(self.expand('svn revert -R .'))
                self.cmd(self.expand('svn switch {{component.url}}'))
                self.cmd(self.expand('svn up -r {{component.revision}}'))


Subversion = Checkout  # BBB
