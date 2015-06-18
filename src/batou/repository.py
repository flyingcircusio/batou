from batou import DeploymentError, output
from batou.utils import cmd
import execnet
import os
import subprocess
import sys
import tempfile


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
        pass

    def update(self, host):
        env = self.environment
        blacklist = ['.batou', 'work', '.git', '.hg', '.vagrant',
                     '.batou-lock']
        for candidate in os.listdir(env.base_dir):
            if candidate in blacklist:
                continue

            source = os.path.join(env.base_dir, candidate)
            target = os.path.join(host.remote_base, candidate)
            output.annotate("rsync source: {}".format(source), debug=True)
            output.annotate("rsync target: {}".format(target), debug=True)
            rsync = execnet.RSync(source, verbose=False)
            rsync.add_target(host.gateway, target)
            rsync.send()


class MercurialRepository(Repository):

    root = None

    def __init__(self, environment):
        super(MercurialRepository, self).__init__(environment)
        self.root = subprocess.check_output(['hg', 'root']).strip()
        self.subdir = os.path.relpath(
            self.environment.base_dir, self.root)

    @property
    def upstream(self):
        if self._upstream is None:
            self._upstream = cmd('hg showconfig paths')[0]
            self._upstream = self._upstream.split('\n')[0].strip()
            assert self._upstream.startswith('paths.default')
            self._upstream = self.upstream.split('=')[1]
        return self._upstream

    def verify(self):
        # Safety belt that we're acting on a clean repository.
        if self.environment.deployment.dirty:
            output.annotate(
                "Dirty deployment - not verifying repository.", red=True)
            return

        try:
            status, _ = cmd('hg -q stat', silent=True)
        except RuntimeError:
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
        except RuntimeError:
            output.error("""\
Your repository has outgoing changes.

I am refusing to deploy in this situation as the results will be unpredictable.
Please push first.
""")
            raise DeploymentError()


class MercurialPullRepository(MercurialRepository):

    def update(self, host):
        env = self.deployment.environment

        self.rpc.pull_code(
            upstream=self.deployment.upstream)

        remote_id = self.rpc.update_working_copy(env.branch)
        local_id, _ = cmd('hg id -i')
        if self.deployment.dirty:
            local_id = local_id.replace('+', '')
        local_id = local_id.strip()
        if remote_id != local_id:
            raise RuntimeError(
                'Working copy parents differ. Local: {} Remote: {}'.format(
                    local_id, remote_id))

        remote_id = self.rpc.update_working_copy(env.branch)
        local_id, _ = cmd('hg id -i')
        if self.deployment.dirty:
            local_id = local_id.replace('+', '')
        local_id = local_id.strip()
        if remote_id != local_id:
            raise RuntimeError(
                'Working copy parents differ. Local: {} Remote: {}'.format(
                    local_id, remote_id))


class MercurialBundleRepository(MercurialRepository):

    def update(self, host):
        heads = host.rpc.current_heads()
        if not heads:
            raise ValueError("Remote repository did not find any heads. "
                             "Can not continue creating a bundle.")
        fd, bundle_file = tempfile.mkstemp()
        os.close(fd)
        bases = ' '.join('--base {}'.format(x) for x in heads)
        cmd('hg -qy bundle {} {}'.format(bases, bundle_file),
            acceptable_returncodes=[0, 1])
        have_changes = os.stat(bundle_file).st_size > 0
        if not have_changes:
            return
        rsync = execnet.RSync(bundle_file, verbose=False)
        rsync.add_target(host.gateway,
                         host.remote_repository + '/batou-bundle.hg')
        rsync.send()
        os.unlink(bundle_file)
        host.rpc.unbundle_code()
