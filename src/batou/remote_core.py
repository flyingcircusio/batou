import logging
import os
import os.path
import shutil
import subprocess
import traceback


# Satisfy flake8 and support testing.
try:
    channel
except NameError:
    channel = None

deployment = None


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


def ensure_repository():
    target = target_directory()
    if not os.path.exists(target):
        os.mkdir(target)
    if not os.path.exists(target+'/.hg'):
        cmd("hg init {}".format(target))
    return target


def current_heads():
    target = target_directory()
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


def pull_code(upstream):
    # TODO Make choice of VCS flexible
    target = target_directory()
    os.chdir(target)
    # Phase 1: update working copy
    # XXX manage certificates
    cmd("hg pull {}".format(upstream))


def unbundle_code():
    # TODO Make choice of VCS flexible
    # XXX does this protect us from accidental new heads?
    target = target_directory()
    os.chdir(target)
    cmd('hg -y unbundle batou-bundle.hg')


def update_working_copy(branch):
    cmd("hg up -C {}".format(branch))
    id = cmd("hg id -i").strip()
    return id


def build_batou(deployment_base):
    target = target_directory()
    os.chdir(os.path.join(target, deployment_base))
    # XXX make cleaning old format optional
    for path in ['develop-eggs', 'bin', 'eggs',
                 'include', 'lib', 'parts', '.installed.cfg']:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.unlink(path)
    cmd('./batou --help')


def setup_deployment(deployment_base, env_name, host_name, overrides):
    from batou.environment import Environment

    target = target_directory()
    os.chdir(os.path.join(target, deployment_base))

    environment = Environment(env_name)
    environment.load()
    environment.overrides = overrides
    environment.configure()

    global deployment
    deployment = Deployment(environment, host_name)


def deploy(root):
    deployment.deploy(root)


def target_directory():
    # XXX make configurable?
    return os.path.expanduser('~/deployment')


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
