from batou import DeploymentError, output, RepositoryDifferentError
from batou.utils import cmd as cmd_, CmdExecutionError
import execnet
import os
import subprocess
import sys
import tempfile


def cmd(c, *args, **kw):
    return cmd_('LANG=C LC_ALL=C LANGUAGE=C {}'.format(c), *args, **kw)


def find_line_with(prefix, output):
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line.replace(prefix, '', 1).strip()


class Repository(object):
    """A repository containing the batou deployment.

    The actual deployment may be located within a prefix
    of this repository. Where the repository starts can be
    determined by the specific repository implementation.

    """

    root = '.'

    def __init__(self, environment):
        self.environment = environment

    @classmethod
    def from_environment(cls, environment):
        if environment.connect_method == 'local':
            return NullRepository(environment)
        elif environment.update_method == 'rsync':
            return RSyncRepository(environment)
        elif environment.update_method == 'hg-bundle':
            return MercurialBundleRepository(environment)
        elif environment.update_method == 'hg-pull':
            return MercurialPullRepository(environment)
        elif environment.update_method == 'git-bundle':
            return GitBundleRepository(environment)
        elif environment.update_method == 'git-pull':
            return GitPullRepository(environment)
        raise ValueError('Could not find method to transfer the repository.')

    def verify(self):
        pass

    def update(self):
        pass


class NullRepository(Repository):
    """A repository that does nothing to verify or update."""


class RSyncRepository(Repository):

    root = '.'

    def verify(self):
        output.annotate(
            "You are using rsync. This is a non-verifying repository "
            "-- continuing on your own risk!", red=True)

    def update(self, host):
        env = self.environment
        blacklist = ['.batou', 'work', '.git', '.hg', '.vagrant', '.kitchen',
                     '.batou-lock']
        for candidate in os.listdir(env.base_dir):
            if candidate in blacklist:
                continue

            source = os.path.join(env.base_dir, candidate)
            target = os.path.join(host.remote_base, candidate)
            output.annotate("rsync: {} -> {}".format(source, target),
                            debug=True)
            rsync = execnet.RSync(source, verbose=False)
            rsync.add_target(host.gateway, target, delete=True)
            rsync.send()


class MercurialRepository(Repository):

    root = None
    _upstream = None

    def __init__(self, environment):
        super(MercurialRepository, self).__init__(environment)
        root_output = subprocess.check_output(['hg', 'root'])
        self.root = root_output.decode(sys.getfilesystemencoding()).strip()
        self.branch = environment.branch or 'default'
        self.subdir = os.path.relpath(
            self.environment.base_dir, self.root)

    @property
    def upstream(self):
        if self.environment.repository_url is not None:
            self._upstream = self.environment.repository_url
        elif self._upstream is None:
            self._upstream = cmd('hg showconfig paths')[0]
            self._upstream = self._upstream.split('\n')[0].strip()
            assert self._upstream.startswith('paths.default')
            self._upstream = self.upstream.split('=')[1]
        return self._upstream

    def update(self, host):
        self._ship(host)
        remote_id = host.rpc.hg_update_working_copy(self.branch)
        local_id, _ = cmd('hg id -i')
        if self.environment.deployment.dirty:
            local_id = local_id.replace('+', '')
        local_id = local_id.strip()
        if remote_id != local_id:
            raise RepositoryDifferentError(local_id, remote_id)

    def verify(self):
        # Safety belt that we're acting on a clean repository.
        if self.environment.deployment.dirty:
            output.annotate(
                "You are running a dirty deployment. This can cause "
                "inconsistencies -- continuing on your own risk!", red=True)
            return

        try:
            status, _ = cmd('hg -q stat')
        except CmdExecutionError:
            output.error('Unable to check repository status. '
                         'Is there an HG repository here?')
            raise
        else:
            status = status.strip()
            if status.strip():
                output.error("Your repository has uncommitted changes.")
                output.annotate("""\
I am refusing to deploy in this situation as the results will be unpredictable.
Please commit and push first.
""", red=True)
                output.annotate(status, red=True)
                raise DeploymentError()
        try:
            cmd('hg -q outgoing -l 1', acceptable_returncodes=[1])
        except CmdExecutionError:
            output.error("""\
Your repository has outgoing changes.

I am refusing to deploy in this situation as the results will be unpredictable.
Please push first.
""")
            raise DeploymentError()


class MercurialPullRepository(MercurialRepository):

    def _ship(self, host):
        host.rpc.hg_pull_code(upstream=self.upstream)


class MercurialBundleRepository(MercurialRepository):

    def _ship(self, host):
        heads = host.rpc.hg_current_heads()
        if not heads:
            raise ValueError("Remote repository did not find any heads. "
                             "Can not continue creating a bundle.")
        fd, bundle_file = tempfile.mkstemp()
        os.close(fd)
        bases = ' '.join('--base {}'.format(x) for x in heads)
        cmd('hg -qy bundle {} {}'.format(bases, bundle_file),
            acceptable_returncodes=[0, 1])
        change_size = os.stat(bundle_file).st_size
        if not change_size:
            return
        output.annotate(
            'Sending {} bytes of changes'.format(change_size), debug=True)
        rsync = execnet.RSync(bundle_file, verbose=False)
        rsync.add_target(host.gateway,
                         host.remote_repository + '/batou-bundle.hg')
        rsync.send()
        os.unlink(bundle_file)
        output.annotate(
            'Unbundling changes', debug=True)
        host.rpc.hg_unbundle_code()


class GitRepository(Repository):

    root = None
    _upstream = None
    remote = 'origin'

    def __init__(self, environment):
        super(GitRepository, self).__init__(environment)
        self.branch = environment.branch or 'master'
        root = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel']).strip()
        self.root = root.decode(sys.getfilesystemencoding())
        self.subdir = os.path.relpath(
            self.environment.base_dir, self.root)

    @property
    def upstream(self):
        if self.environment.repository_url is not None:
            self._upstream = self.environment.repository_url
        elif self._upstream is None:
            result = cmd('git remote show -n {}'.format(self.remote))[0]
            self._upstream = find_line_with('Fetch URL:', result)
        return self._upstream

    def update(self, host):
        self._ship(host)
        remote_id = host.rpc.git_update_working_copy(self.branch)
        # This can theoretically fail if we have a fresh repository, but
        # that doesn't make sense at this point anyway.
        local_id, _ = cmd('git rev-parse HEAD')
        local_id = local_id.strip()
        if remote_id != local_id:
            raise RepositoryDifferentError(local_id, remote_id)

    def verify(self):
        # Safety belt that we're acting on a clean repository.
        if self.environment.deployment.dirty:
            output.annotate(
                "You are running a dirty deployment. This can cause "
                "inconsistencies -- continuing on your own risk!", red=True)
            return

        try:
            status, _ = cmd('git status --porcelain')
        except CmdExecutionError:
            output.error('Unable to check repository status. '
                         'Is there a Git repository here?')
            raise
        else:
            status = status.strip()
            if status.strip():
                output.error("Your repository has uncommitted changes.")
                output.annotate("""\
I am refusing to deploy in this situation as the results will be unpredictable.
Please commit and push first.
""", red=True)
                output.annotate(status, red=True)
                raise DeploymentError()
        outgoing, _ = cmd(
            'git log {remote}/{branch}..{branch} --pretty=oneline'.format(
                remote=self.remote, branch=self.branch),
            acceptable_returncodes=[0, 128])
        if outgoing.strip():
            output.error("""\
Your repository has outgoing changes.

I am refusing to deploy in this situation as the results will be unpredictable.
Please push first.
""")
            raise DeploymentError()


class GitPullRepository(GitRepository):

    def _ship(self, host):
        host.rpc.git_pull_code(upstream=self.upstream,
                               branch=self.branch)


class GitBundleRepository(GitRepository):

    def _ship(self, host):
        head = host.rpc.git_current_head()
        if head is None:
            bundle_range = self.branch
        else:
            head = head.decode('ascii')
            bundle_range = '{head}..{branch}'.format(
                head=head, branch=self.branch)
        fd, bundle_file = tempfile.mkstemp()
        os.close(fd)
        out, err = cmd('git bundle create {file} {range}'.format(
            file=bundle_file, range=bundle_range),
            acceptable_returncodes=[0, 128])
        if 'create empty bundle' in err:
            return
        change_size = os.stat(bundle_file).st_size
        output.annotate(
            'Sending {} bytes of changes'.format(change_size), debug=True)
        rsync = execnet.RSync(bundle_file, verbose=False)
        rsync.add_target(host.gateway,
                         host.remote_repository + '/batou-bundle.git')
        rsync.send()
        os.unlink(bundle_file)
        output.annotate(
            'Unbundling changes', debug=True)
        host.rpc.git_unbundle_code()
