import logging
import os
import os.path
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


def update_code(upstream):
    # TODO Make choice of VCS flexible
    target = target_directory()
    if not os.path.exists(target):
        os.mkdir(target)
        cmd("hg init {}".format(target))
    os.chdir(target)
    # Phase 1: update working copy
    # XXX manage certificates
    cmd("hg pull {}".format(upstream))
    cmd("hg up -C")
    id = cmd("hg id -i")
    return target, id


def build_batou(deployment_base):
    target = target_directory()
    os.chdir(os.path.join(target, deployment_base))
    # XXX make cleaning old format optional
    for path in ['develop-eggs', 'bin', 'eggs', 'include', 'lib', 'parts', '.installed.cfg']:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.unlink(path)
    cmd('batou --help')
    cmd('bin/buildout -t 15')


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
