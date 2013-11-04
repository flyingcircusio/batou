from batou import UpdateNeeded
from batou.component import Component
from batou.lib.file import Directory
import os.path
import re


class Clone(Component):

    namevar = 'url'
    target = '.'
    revision = None
    branch = None

    _revision_pattern = re.compile('parent: \d+:([a-f0-9]+) ')

    def configure(self):
        assert self.revision_or_branch
        self.target = self.map(self.target)
        self += Directory(self.target)

    def verify(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                raise UpdateNeeded()
            if self.revision and self.current_revision != self.revision:
                raise UpdateNeeded()
            if (self.branch and (
                    self.current_branch != self.branch or
                    self.has_incoming_changesets)):
                raise UpdateNeeded()

    @property
    def revision_or_branch(self):
        # Mercurial often takes either a revision or a branch.
        return self.revision or self.branch

    @property
    def current_revision(self):
        stdout, stderr = self.cmd(
            self.expand('LANG=C hg --cwd {{component.target}} summary | '
                        'grep parent:'))
        match = self._revision_pattern.search(stdout)
        if not match:
            return None
        return match.group(1)

    @property
    def current_branch(self):
        stdout, stderr = self.cmd('hg branch')
        return stdout.strip()

    @property
    def has_incoming_changesets(self):
        try:
            self.cmd('hg incoming -q -l1', silent=True)
        except RuntimeError, e:
            returncode = e.args[1]
            if returncode == 1:
                return False
            raise
        return True

    def update(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                self.cmd(self.expand(
                    'hg clone -u {{component.revision_or_branch}} '
                    '{{component.url}} .'))
            else:
                self.cmd('hg pull')
                self.cmd(self.expand(
                    'hg up --clean {{component.revision_or_branch}}'))

    def last_updated(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                return None
            stdout, stderr = self.cmd(
                'hg log -r %s --template "{date|hgdate}\n"' %
                self.current_revision)
            timestamp, offset = stdout.split()
            return float(timestamp) - float(offset)
