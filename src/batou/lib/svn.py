from batou import UpdateNeeded
from batou.component import Component
from batou.lib.file import Directory
import os.path


class Subversion(Component):

    namevar = 'url'
    target = '.'
    revision = None

    _needs_upgrade = False

    def configure(self):
        self += Directory(self.target)

    def verify(self):
        with self.chdir(self.target):
            if not os.path.exists('.svn'):
                raise UpdateNeeded()
            try:
                stdout, stderr = (
                    self.cmd('svn info | grep Revision:', silent=True))
            except RuntimeError, e:
                stderr = e.args[3]
                if 'E155036' in stderr:
                    self._needs_upgrade = True
                    raise UpdateNeeded()
                # Unknown error condition, don't hide.
                raise
            current_revision = stdout.replace('Revision:', '').strip()
            if current_revision != self.revision:
                raise UpdateNeeded()

    def _upgrade(self):
        if not self._needs_upgrade:
            return
        self.cmd('svn upgrade --non-interactive')

    def update(self):
        with self.chdir(self.target):
            if not os.path.exists('.svn'):
                self.cmd(self.expand(
                    'svn co {{component.url}} . -r {{component.revision}}'))
            else:
                self._upgrade()
                self.cmd(self.expand('svn revert -R .'))
                self.cmd(self.expand('svn switch {{component.url}}'))
                self.cmd(self.expand('svn up -r {{component.revision}}'))
