from batou import UpdateNeeded, output
from batou.component import Component
from batou.lib.file import Directory, ensure_path_nonexistent
import os.path


def ensure_empty_directory(path):
    """Ensure path is an empty directory.

    Keep the directory if it exists or create a new one if it
    didn't or if it wasn't a directory.

    This helps in situations where the current workdir may be
    the existing path that needs to be cleaned up.
    """
    if not os.path.isdir(path):
        ensure_path_nonexistent(path)
        os.makedirs(path)
    for file in os.listdir(path):
        ensure_path_nonexistent(os.path.join(path, file))


class Clone(Component):

    namevar = 'url'
    target = '.'
    revision = None
    branch = None
    vcs_update = True

    def configure(self):
        if (not self.revision_or_branch) or (self.revision and self.branch):
            raise ValueError(
                'Clone(%s) needs exactly one of revision or branch' % self.url)
        self.target = self.map(self.target)
        self += Directory(self.target)

    def verify(self):
        self._force_clone = False
        if not os.path.exists(self.target):
            self._force_clone = True
            raise UpdateNeeded()
        # if the path does exist but isn't a directory, just let the error
        # bubble for now, the message will at least tell something useful
        with self.chdir(self.target):
            if not os.path.exists('.git'):
                self._force_clone = True
                raise UpdateNeeded()

            if self.remote_url() != self.url:
                self._force_clone = True
                raise UpdateNeeded()

            if not self.vcs_update:
                return

            if self.has_outgoing_changesets():
                output.annotate(
                    'Git clone at {} has outgoing changesets.'.format(
                        self.target))

            if self.has_changes():
                output.annotate(
                    'Git clone at {} is dirty, going to lose changes.'.format(
                        self.target), red=True)
                raise UpdateNeeded()

            if self.revision and self.current_revision() != self.revision:
                raise UpdateNeeded()
            if (self.branch and (
                    self.current_branch() != self.branch or
                    self.has_incoming_changesets())):
                raise UpdateNeeded()

    @property
    def revision_or_branch(self):
        return self.revision or self.branch

    def current_revision(self):
        try:
            with self.chdir(self.target):
                stdout, stderr = self.cmd('LANG=C git show -s --format=%H')
        except RuntimeError:
            return None
        return stdout.strip()

    def current_branch(self):
        with self.chdir(self.target):
            stdout, stderr = self.cmd('git rev-parse --abbrev-ref HEAD')
        return stdout.strip()

    def has_incoming_changesets(self):
        with self.chdir(self.target):
            stdout, stderr = self.cmd('git fetch --dry-run')
            return stderr.strip()

    def has_outgoing_changesets(self):
        with self.chdir(self.target):
            stdout, stderr = self.cmd('LANG=C git status')
        return 'Your branch is ahead of' in stdout

    def has_changes(self):
        with self.chdir(self.target):
            stdout, stderr = self.cmd('git status --porcelain')
        return bool(stdout.strip())

    def remote_url(self):
        with self.chdir(self.target):
            stdout, stderr = self.cmd('git remote get-url origin')
        return stdout.strip()

    def update(self):
        just_cloned = False
        if self._force_clone:
            ensure_empty_directory(self.target)
            self.cmd(self.expand(
                'git clone {{component.url}} {{component.target}}'))
            just_cloned = True
        with self.chdir(self.target):
            for filepath in self.untracked_files():
                os.unlink(os.path.join(self.target, filepath))
            if not just_cloned:
                self.cmd('git fetch')
            if self.branch:
                self.cmd(self.expand(
                    'git reset --hard origin/{{component.branch}}'))
            else:
                self.cmd(self.expand(
                    'git reset --hard {{component.revision}}'))

            # XXX We should re-think submodule support; e.g. which revision
            # shall the submodules be updated to?
            self.cmd('git submodule update --init --recursive')

    def untracked_files(self):
        stdout, stderr = self.cmd(
            'git status --porcelain --untracked-files=all')
        items = (line.split(None, 1) for line in stdout.splitlines())
        return [filepath for status, filepath in items if status == '??']

    def last_updated(self):
        with self.chdir(self.target):
            if not os.path.exists('.git'):
                return None
            stdout, stderr = self.cmd('git show -s --format=%ct')
            timestamp = stdout.strip()
            return float(timestamp)
