from batou import UpdateNeeded, output
from batou.component import Component
from batou.lib.file import Directory
from batou.utils import CmdExecutionError
import os.path
import re


class Clone(Component):

    namevar = 'url'
    target = '.'
    revision = None
    branch = None
    vcs_update = True

    _revision_pattern = re.compile(r'changeset: +\d+:([a-f0-9]+)')

    def configure(self):
        if (not self.revision_or_branch) or (self.revision and self.branch):
            raise ValueError(
                'Clone(%s) needs exactly one of revision or branch' % self.url)
        self.target = self.map(self.target)
        self += Directory(self.target)

    def verify(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                raise UpdateNeeded()

            if not self.vcs_update:
                return

            if self.has_outgoing_changesets():
                output.annotate(
                    'Hg clone at {} has outgoing changesets.'.format(
                        self.target), red=True)

            if self.has_changes():
                output.annotate(
                    'Hg clone at {} is dirty, going to lose changes.'.format(
                        self.target), red=True)
                raise UpdateNeeded()

            if self.revision:
                long_rev = len(self.revision) == 40
                if self.current_revision(long_rev) != self.revision:
                    raise UpdateNeeded()
            if (self.branch and (
                    self.current_branch() != self.branch or
                    self.has_incoming_changesets())):
                raise UpdateNeeded()

    @property
    def revision_or_branch(self):
        # Mercurial often takes either a revision or a branch.
        return self.revision or self.branch

    def current_revision(self, long=False):
        debug = '--debug' if long else ''
        stdout, stderr = self.cmd(
            self.expand(
                'LANG=C hg --cwd {{component.target}} {{debug}} parent | '
                'grep changeset:',
                debug=debug))
        match = self._revision_pattern.search(stdout)
        if not match:
            return None
        return match.group(1)

    def current_branch(self):
        stdout, stderr = self.cmd('hg branch')
        return stdout.strip()

    def has_incoming_changesets(self):
        try:
            self.cmd('hg incoming -q -l1')
        except CmdExecutionError as e:
            if e.returncode == 1:
                return False
            raise
        return True

    def has_outgoing_changesets(self):
        try:
            with self.chdir(self.target):
                self.cmd('hg outgoing -q -l1')
        except CmdExecutionError as e:
            if e.returncode == 1:
                return False
            raise
        return True

    def has_changes(self):
        with self.chdir(self.target):
            stdout, stderr = self.cmd('hg status')
        return bool(stdout.strip())

    def update(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                self.cmd(self.expand(
                    'hg clone -u {{component.revision_or_branch}} '
                    '{{component.url}} .'))
                return
            self.cmd(self.expand(
                'hg pull --rev {{component.revision_or_branch}}'))
            for filepath in self.untracked_files():
                os.unlink(os.path.join(self.target, filepath))
            self.cmd(self.expand(
                'hg update --clean --rev {{component.revision_or_branch}}'))

    def untracked_files(self):
        stdout, stderr = self.cmd('hg status -q -u')
        items = (line.split(None, 1) for line in stdout.splitlines())
        return [filepath for status, filepath in items if status == '?']

    def last_updated(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                return None
            stdout, stderr = self.cmd(
                'hg log -r %s --template "{date|hgdate}\n"' %
                self.current_revision())
            timestamp, offset = stdout.split()
            return float(timestamp) - float(offset)
