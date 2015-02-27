import logging
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
target_directory = None


class Deployment(object):

    environment = None

    def __init__(self, environment, host):
        self.environment = environment
        self.host = host

    def deploy(self, root):
        root = self.environment.get_root(root, self.host)
        root.component.deploy()


def lock():
    # XXX implement!
    pass


def cmd(c):
    return subprocess.check_output(
        [c], shell=True)


def ensure_repository(target, method):
    target = os.path.expanduser(target)
    global target_directory
    target_directory = target

    if not os.path.exists(target):
        os.mkdir(target)

    if method in ['pull', 'bundle']:
        if not os.path.exists(target + '/.hg'):
            cmd("hg init {}".format(target))

    return target


def current_heads():
    target = target_directory
    os.chdir(target)
    result = []
    id = cmd('hg id -i').strip()
    if id == '000000000000':
        return [id]
    heads = cmd('LANG=C LC_ALL=C LANGUAGE=C hg heads')
    for line in heads.split('\n'):
        if not line.startswith('changeset:'):
            continue
        line = line.split(':')
        result.append(line[2])
    return result


def pull_code(upstream):
    # TODO Make choice of VCS flexible
    target = target_directory
    os.chdir(target)
    # Phase 1: update working copy
    # XXX manage certificates
    cmd("hg pull {}".format(upstream))


def unbundle_code():
    # TODO Make choice of VCS flexible
    # XXX does this protect us from accidental new heads?
    target = target_directory
    os.chdir(target)
    cmd('hg -y unbundle batou-bundle.hg')


def update_working_copy(branch):
    cmd("hg up -C {}".format(branch))
    id = cmd("hg id -i").strip()
    return id


def build_batou(deployment_base):
    target = target_directory
    os.chdir(os.path.join(target, deployment_base))
    cmd('./batou --help')


def setup_deployment(deployment_base, env_name, host_name, overrides):
    from batou.environment import Environment

    target = target_directory
    os.chdir(os.path.join(target, deployment_base))

    environment = Environment(env_name)
    environment.load()
    environment.overrides = overrides
    environment.configure()

    global deployment
    deployment = Deployment(environment, host_name)


def deploy(root):
    deployment.deploy(root)


def roots_in_order():
    result = []
    for root in deployment.environment.roots_in_order():
        result.append((root.host.fqdn, root.name))
    return result


def whoami():
    return pwd.getpwuid(os.getuid()).pw_name


def setup_logging(loggers, level):
    ch = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    for logger in loggers:
        logger = logging.getLogger(logger)
        logger.setLevel(level)
        logger.addHandler(ch)


def send_file(name):
    code = None
    with open(name, 'w') as f:
        while code != 'finish':
            code, data = channel.receive()
            f.write(data)
    return 'OK'


if __name__ == '__channelexec__':
    setup_logging(['batou'], logging.INFO)
    while not channel.isclosed():
        task, args, kw = channel.receive()
        try:
            result = locals()[task](*args, **kw)
        except Exception, e:
            tb = traceback.format_exc()
            result = ('batou-remote-core-error', tb)
        channel.send(result)
