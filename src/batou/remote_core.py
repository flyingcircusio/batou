import os
import os.path
import pwd
import subprocess
import traceback


# Satisfy flake8 and support testing.
try:
    channel
except NameError:
    channel = None


deployment = None
environment = None
target_directory = None


class Deployment(object):

    environment = None

    def __init__(self, env_name, host_name, overrides,
                 timeout, platform):
        self.env_name = env_name
        self.host_name = host_name
        self.overrides = overrides
        self.timeout = timeout
        self.platform = platform

    def load(self):
        from batou.environment import Environment
        self.environment = Environment(
            self.env_name, self.timeout, self.platform)
        self.environment.deployment = self
        self.environment.load()
        self.environment.overrides = self.overrides
        self.environment.configure()

    def deploy(self, root):
        root = self.environment.get_root(root, self.host_name)
        root.component.deploy()


def lock():
    # XXX implement!
    pass


class CmdError(Exception):

    def __init__(self, orig_exception):
        self.orig_exception = orig_exception

    def report(self):
        try:
            from batou import output
        except ImportError:
            pass
        else:
            output.line('asdf', red=True)


def cmd(c, acceptable_returncodes=[0]):
    process = subprocess.Popen(
        ['LANG=C LC_ALL=C LANGUAGE=C {}'.format(c)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        shell=True)
    stdout, stderr = process.communicate()
    if process.returncode not in acceptable_returncodes:
        error = subprocess.CalledProcessError(
            process.returncode, c)
        raise CmdError(error)
    return stdout, stderr


def ensure_repository(target, method):
    target = os.path.expanduser(target)
    global target_directory
    target_directory = target

    if not os.path.exists(target):
        os.makedirs(target)

    if method in ['hg-pull', 'hg-bundle']:
        if not os.path.exists(target + '/.hg'):
            cmd("hg init {}".format(target))
    elif method in ['git-pull', 'git-bundle']:
        if not os.path.exists(target + '/.git'):
            cmd("git init {}".format(target))
    elif method == 'rsync':
        pass
    else:
        raise RuntimeError("Unknown repository method: {}".format(method))

    return target


def ensure_base(base):
    base = os.path.join(target_directory, base)
    if not os.path.exists(base):
        os.makedirs(base)
    return base


def hg_current_heads():
    target = target_directory
    os.chdir(target)
    result = []
    id = cmd('hg id -i').strip()
    if id == '000000000000':
        return [id]
    heads = cmd('hg heads')
    for line in heads.split('\n'):
        if not line.startswith('changeset:'):
            continue
        line = line.split(':')
        result.append(line[2])
    return result


def hg_pull_code(upstream):
    # TODO Make choice of VCS flexible
    target = target_directory
    os.chdir(target)
    # Phase 1: update working copy
    # XXX manage certificates
    cmd("hg pull {}".format(upstream))


def hg_unbundle_code():
    # TODO Make choice of VCS flexible
    # XXX does this protect us from accidental new heads?
    target = target_directory
    os.chdir(target)
    cmd('hg -y unbundle batou-bundle.hg')


def hg_update_working_copy(branch):
    cmd("hg up -C {}".format(branch))
    id = cmd("hg id -i").strip()
    return id


def git_current_head(branch):
    target = target_directory
    os.chdir(target)
    id, err = cmd('git rev-parse {branch}'.format(branch=branch),
                  acceptable_returncodes=[0, 128])
    id = id.strip()
    return id if 'unknown revision' not in err else None


def git_pull_code(upstream):
    target = target_directory
    os.chdir(target)
    cmd("git fetch {upstream}".format(upstream=upstream))


def git_unbundle_code():
    target = target_directory
    os.chdir(target)
    out, err = cmd('git remote -v')
    if 'bundle' not in out:
        cmd('git remote add bundle batou-bundle.git')
    cmd('git fetch bundle')


def git_update_working_copy(branch):
    cmd('git checkout --force {branch}'.format(branch=branch))
    id, _ = cmd('git rev-parse HEAD')
    return id.strip()


def build_batou(deployment_base, bootstrap, fast=False):
    target = target_directory
    os.chdir(os.path.join(target, deployment_base))
    with open('batou', 'w') as f:
        f.write(bootstrap)
    os.chmod('batou', 0o755)
    cmd('./batou {}--help'.format('--fast ' if fast else ''))


def setup_deployment(
        deployment_base, *args):
    target = target_directory
    os.chdir(os.path.join(target, deployment_base))
    global deployment
    deployment = Deployment(*args)
    deployment.load()


def deploy(root):
    deployment.deploy(root)


def roots_in_order():
    result = []
    for root in deployment.environment.roots_in_order():
        result.append((root.host.fqdn, root.name))
    return result


def whoami():
    return pwd.getpwuid(os.getuid()).pw_name


def setup_output():
    from batou._output import output, ChannelBackend
    output.backend = ChannelBackend(channel)


if __name__ == '__channelexec__':
    while not channel.isclosed():
        task, args, kw = channel.receive()
        # Support slow bootstrapping
        try:
            import batou
        except ImportError:
            batou = None
        try:
            result = locals()[task](*args, **kw)
            channel.send(('batou-result', result))
        except getattr(batou, 'ConfigurationError', None) as e:
            if e not in deployment.environment.exceptions:
                deployment.environment.exceptions.append(e)
            # Report on why configuration failed.
            for exception in deployment.environment.exceptions:
                exception.report()
            batou.output.section(
                "{} ERRORS - CONFIGURATION FAILED".format(
                    len(deployment.environment.exceptions)), red=True)
            channel.send(('batou-error', None))
        except getattr(batou, 'DeploymentError', None) as e:
            e.report()
            channel.send(('batou-error', None))
        except Exception as e:
            # I voted for duck-typing here as we may be running in the
            # bootstrapping phase and don't have access to all classes yet.
            if hasattr(e, 'report'):
                e.report()
                channel.send(('batou-error', None))
            else:
                tb = traceback.format_exc()
                channel.send(('batou-unknown-error', tb))
