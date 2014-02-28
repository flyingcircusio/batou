from batou import UpdateNeeded
from batou.component import Component
from batou.lib.file import Directory
import logging
import os.path
import re


logger = logging.getLogger(__name__)


class Clone(Component):

    namevar = 'url'
    target = '.'
    revision = None
    branch = None
    vcs_update = True

    _revision_pattern = re.compile('parent: \d+:([a-f0-9]+) ')

    def configure(self):
        assert self.revision_or_branch
        self.target = self.map(self.target)
        self += Directory(self.target)

    def verify(self):
        with self.chdir(self.target):
            if not os.path.exists('.hg'):
                raise UpdateNeeded()

            if not self.vcs_update:
                return

            if self.has_outgoing_changesets:
                logger.info(
                    'Hg clone at {} has outgoing changesets.'.format(
                        self.target))

            if self.has_changes:
                logger.warning(
                    'Hg clone at {} is dirty, going to lose changes.'.format(
                        self.target))
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

    @property
    def has_outgoing_changesets(self):
        try:
            with self.chdir(self.target):
                self.cmd('hg outgoing -q -l1', silent=True)
        except RuntimeError, e:
            returncode = e.args[1]
            if returncode == 1:
                return False
            raise
        return True

    @property
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
            for filepath in self.untracked_files:
                os.unlink(os.path.join(self.target, filepath))
            self.cmd(self.expand(
                'hg update --clean --rev {{component.revision_or_branch}}'))

    @property
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
                self.current_revision)
            timestamp, offset = stdout.split()
            return float(timestamp) - float(offset)
