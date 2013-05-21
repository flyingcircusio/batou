from batou import UpdateNeeded
from batou.component import Component
from batou.lib.file import Directory
import os.path
import re


class Clone(Component):

    namevar = 'url'
    target = '.'
    revision = None

    _revision_pattern = re.compile('parent: \d+:([a-f0-9]+) ')

    def configure(self):
        self += Directory(self.target)

    def verify(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                raise UpdateNeeded()
            if self.current_revision != self.revision:
                raise UpdateNeeded()

    @property
    def current_revision(self):
        stdout, stderr = self.cmd('LANG=C hg summary | grep parent:')
        match = self._revision_pattern.search(stdout)
        if not match:
            return None
        return match.group(1)

    def update(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                self.cmd(self.expand(
                    'hg clone -u {{component.revision}} {{component.url}} .'))
            else:
                self.cmd('hg pull')
                self.cmd(self.expand('hg up --clean {{component.revision}}'))

    def last_updated(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                return None
            stdout, stderr = self.cmd(
                'hg log -r %s --template "{date|hgdate}\n"' %
                self.current_revision)
            timestamp, offset = stdout.split()
            return float(timestamp) - float(offset)
