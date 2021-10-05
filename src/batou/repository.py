import json
import os
import subprocess
import sys
import tempfile

import execnet

from batou import DeploymentError, RepositoryDifferentError, output
from batou.utils import CmdExecutionError
from batou.utils import cmd as cmd_


def cmd(c, *args, **kw):
    return cmd_("LANG=C LC_ALL=C LANGUAGE=C {}".format(c), *args, **kw)


def find_line_with(prefix, output):
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line.replace(prefix, "", 1).strip()


class Repository(object):
    """A repository containing the batou deployment.

    The actual deployment may be located within a prefix
    of this repository. Where the repository starts can be
    determined by the specific repository implementation.

    """

    def __init__(self, environment):
        self.environment = environment
        # We can't set this default on the environment because we
        # have a special use of None for test support.
        self.root = environment.repository_root or '.'

    @classmethod
    def from_environment(cls, environment):
        if environment.connect_method == "local":
            return NullRepository(environment)
        elif environment.update_method == "rsync":
            return RSyncRepository(environment)
        elif environment.update_method == "hg-bundle":
            return MercurialBundleRepository(environment)
        elif environment.update_method == "hg-pull":
            return MercurialPullRepository(environment)
        elif environment.update_method == "git-bundle":
            return GitBundleRepository(environment)
        elif environment.update_method == "git-pull":
            return GitPullRepository(environment)
        raise ValueError("Could not find method to transfer the repository.")

    def verify(self):
        pass

    def update(self, host):
        pass


class NullRepository(Repository):
    """A repository that does nothing to verify or update."""


class FilteredRSync(execnet.RSync):
    """Implement a filtered RSync that
    avoids copying files from our blacklist.
    """

    IGNORE_LIST = (
        ".appenv",
        ".batou",
        ".batou-lock",
        ".git",
        ".hg",
        ".kitchen",
        ".vagrant",
        "work",
    )

    def __init__(self, *args, **kw):
        super(FilteredRSync, self).__init__(*args, **kw)
        self.IGNORE_LIST = set(self.IGNORE_LIST)

    def filter(self, path):
        return os.path.basename(path) not in self.IGNORE_LIST


class RSyncRepository(Repository):

    def verify(self):
        output.annotate(
            "You are using rsync. This is a non-verifying repository "
            "-- continuing on your own risk!",
            red=True)

    def update(self, host):
        source, target = self.root, host.remote_repository
        output.annotate("rsync: {} -> {}".format(source, target), debug=True)
        rsync = FilteredRSync(source, verbose=False)
        # We really want to use `delete=True` here but there's an execnet issue
        # preventing us to use it. See
        # https://github.com/flyingcircusio/batou/issues/107
        rsync.add_target(host.gateway, target)
        rsync.send()


def hg_cmd(hgcmd):
    output, _ = cmd(hgcmd + " -Tjson")
    output = json.loads(output)
    return output


class MercurialRepository(Repository):

    root = None
    _upstream = None

    def __init__(self, environment):
        super(MercurialRepository, self).__init__(environment)
        self.root = hg_cmd("hg root")[0]["reporoot"]
        self.branch = environment.branch or "default"
        self.subdir = os.path.relpath(self.environment.base_dir, self.root)

    @property
    def upstream(self):
        if self.environment.repository_url is not None:
            self._upstream = self.environment.repository_url
        elif self._upstream is None:
            for item in hg_cmd("hg showconfig paths"):
                if item['name'] != "paths.default":
                    continue
                self._upstream = item['value']
                break
            else:
                raise AssertionError("`paths.default` not found")
        return self._upstream

    def update(self, host):
        self._ship(host)
        remote_id = host.rpc.hg_update_working_copy(self.branch)
        local_id = hg_cmd("hg id")[0]['id']
        if self.environment.deployment.dirty:
            local_id = local_id.replace("+", "")
        if remote_id != local_id:
            raise RepositoryDifferentError(local_id, remote_id)

    def verify(self):
        # Safety belt that we're acting on a clean repository.
        if self.environment.deployment.dirty:
            output.annotate(
                "You are running a dirty deployment. This can cause "
                "inconsistencies -- continuing on your own risk!",
                red=True)
            return

        try:
            status = hg_cmd("hg stat")
        except CmdExecutionError:
            output.error("Unable to check repository status. "
                         "Is there an HG repository here?")
            raise
        else:
            if status:
                output.error("Your repository has uncommitted changes.")
                output.annotate(
                    """\
I am refusing to deploy in this situation as the results will be unpredictable.
Please commit and push first.
""",
                    red=True)
                for item in status:
                    output.annotate(
                        "{} {}".format(item['status'], item['path']), red=True)
                raise DeploymentError("Uncommitted changes")
        try:
            cmd("hg -q outgoing -l 1", acceptable_returncodes=[1])
        except CmdExecutionError:
            output.error("""\
Your repository has outgoing changes.

I am refusing to deploy in this situation as the results will be unpredictable.
Please push first.
""")
            raise DeploymentError("Outgoing changes")


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
        bases = " ".join("--base {}".format(x) for x in heads)
        cmd("hg -qy bundle {} {}".format(bases, bundle_file),
            acceptable_returncodes=[0, 1])
        change_size = os.stat(bundle_file).st_size
        if not change_size:
            return
        output.annotate(
            "Sending {} bytes of changes".format(change_size), debug=True)
        rsync = execnet.RSync(bundle_file, verbose=False)
        rsync.add_target(host.gateway,
                         host.remote_repository + "/batou-bundle.hg")
        rsync.send()
        os.unlink(bundle_file)
        output.annotate("Unbundling changes", debug=True)
        host.rpc.hg_unbundle_code()


class GitRepository(Repository):

    root = None
    _upstream = None
    remote = "origin"

    def __init__(self, environment):
        super(GitRepository, self).__init__(environment)
        self.branch = environment.branch or "master"
        root = subprocess.check_output(["git", "rev-parse",
                                        "--show-toplevel"]).strip()
        self.root = root.decode(sys.getfilesystemencoding())
        self.subdir = os.path.relpath(self.environment.base_dir, self.root)

    @property
    def upstream(self):
        if self.environment.repository_url is not None:
            self._upstream = self.environment.repository_url
        elif self._upstream is None:
            result = cmd("git remote show -n {}".format(self.remote))[0]
            self._upstream = find_line_with("Fetch URL:", result)
        return self._upstream

    def update(self, host):
        self._ship(host)
        remote_id = host.rpc.git_update_working_copy(self.branch)
        # This can theoretically fail if we have a fresh repository, but
        # that doesn't make sense at this point anyway.
        local_id, _ = cmd("git rev-parse HEAD")
        local_id = local_id.strip()
        if remote_id != local_id:
            raise RepositoryDifferentError(local_id, remote_id)

    def verify(self):
        # Safety belt that we're acting on a clean repository.
        if self.environment.deployment.dirty:
            output.annotate(
                "You are running a dirty deployment. This can cause "
                "inconsistencies -- continuing on your own risk!",
                red=True)
            return

        try:
            status, _ = cmd("git status --porcelain")
        except CmdExecutionError:
            output.error("Unable to check repository status. "
                         "Is there a Git repository here?")
            raise
        else:
            status = status.strip()
            if status.strip():
                output.error("Your repository has uncommitted changes.")
                output.annotate(
                    """\
I am refusing to deploy in this situation as the results will be unpredictable.
Please commit and push first.
""",
                    red=True)
                output.annotate(status, red=True)
                raise DeploymentError()
        outgoing, _ = cmd(
            "git log {remote}/{branch}..{branch} --pretty=oneline".format(
                remote=self.remote, branch=self.branch),
            acceptable_returncodes=[0, 128])
        if outgoing.strip():
            output.error("""\
Your repository has outgoing changes on branch {branch}:

{outgoing}

I am refusing to deploy in this situation as the results will be unpredictable.
Please push first.
""".format(branch=self.branch, outgoing=outgoing))
            raise DeploymentError()


class GitPullRepository(GitRepository):

    def _ship(self, host):
        host.rpc.git_pull_code(upstream=self.upstream, branch=self.branch)


class GitBundleRepository(GitRepository):

    def _ship(self, host):
        head = host.rpc.git_current_head()
        if head is None:
            bundle_range = self.branch
        else:
            head = head.decode("ascii")
            bundle_range = "{head}..{branch}".format(
                head=head, branch=self.branch)
        fd, bundle_file = tempfile.mkstemp()
        os.close(fd)
        out, err = cmd(
            "git bundle create {file} {range}".format(
                file=bundle_file, range=bundle_range),
            acceptable_returncodes=[0, 128])
        if "create empty bundle" in err:
            return
        change_size = os.stat(bundle_file).st_size
        output.annotate(
            "Sending {} bytes of changes".format(change_size), debug=True)
        rsync = execnet.RSync(bundle_file, verbose=False)
        rsync.add_target(host.gateway,
                         host.remote_repository + "/batou-bundle.git")
        rsync.send()
        os.unlink(bundle_file)
        output.annotate("Unbundling changes", debug=True)
        host.rpc.git_unbundle_code()
