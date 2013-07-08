import os
import os.path
import subprocess

# Satisfy flake8 and support testing.
try:
    channel
except NameError:
    channel = None

host = None


def lock():
    # XXX implement!
    pass


def cmd(c):
    return subprocess.check_output(
        [c], shell=True)


def update_code(upstream):
    # TODO Make choice of VCS flexible
    base = get_deployment_base()
    if not os.path.exists(base):
        cmd("hg init {}".format(base))
    os.chdir(base)
    # Phase 1: update working copy
    # XXX manage certificates
    cmd("hg pull {}".format(upstream))
    cmd("hg up -C")
    id = cmd("hg id -i")
    return base, id


def build_batou(service_base):
    base = get_deployment_base()
    os.chdir(os.path.join(base, service_base))
    if not os.path.exists('bin/python2.7'):
        cmd('virtualenv --no-site-packages --python python2.7 .')
    if not os.path.exists('bin/buildout'):
        cmd('bin/easy_install-2.7 -U setuptools')
        cmd('bin/python2.7 bootstrap.py')
    cmd('bin/buildout -t 15')


def setup_service(service_base, env_name, host_name, overrides):
    from batou.service import ServiceConfig
    global host

    base = get_deployment_base()
    os.chdir(os.path.join(base, service_base))

    config = ServiceConfig('.', [env_name])
    config.scan()
    environment = config.service.environments[env_name]
    environment.overrides = overrides
    environment.configure()
    host = environment.get_host(host_name)


def deploy_component(component_name):
    global host
    host[component_name].deploy()


def get_deployment_base():
    # XXX make configurable?
    return os.path.expanduser('~/deployment')


if __name__ == '__channelexec__':
    while not channel.isclosed():
        # Allow other channels to interleave with our mainloop
        try:
            task, args, kw = channel.receive(0.1)
        except channel.TimeoutError:
            pass
        else:
            result = locals()[task](*args, **kw)
            channel.send(result)
