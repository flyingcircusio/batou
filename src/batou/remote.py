from . import remote_core
from .environment import Environment
from .utils import notify, cmd
import execnet
import logging
import os
import os.path
import subprocess
import sys

# XXX reset

logger = logging.getLogger('batou.remote')


def main(environment):
    check_clean_hg_repository()

    environment = Environment(environment)
    environment.load()
    environment.load_secrets()
    environment.configure()

    deployment = RemoteDeployment(environment)
    try:
        deployment()
    except Exception, e:
        logger.exception(e)
    else:
        notify('Deployment finished',
               '{} was deployed successfully.'.format(environment.name))


def check_clean_hg_repository():
    # Safety belt that we're acting on a clean repository.
    try:
        status, _ = cmd('hg -q stat', silent=True)
    except RuntimeError:
        logger.error('Unable to check repository status. '
                     'Is there an HG repository here?')
        sys.exit(1)
    else:
        status = status.strip()
        if status.strip():
            logger.error(
                'Refusing to deploy remotely with a dirty working copy:')
            logger.error(status)
            sys.exit(1)

    try:
        cmd('hg -q outgoing -l 1', silent=True)
    except RuntimeError, e:
        if e.args[1] == 1 and not e.args[2] and not e.args[3]:
            # this means there' snothing outgoing
            pass
        else:
            raise
    else:
        logger.error('Refusing to deploy with outgoing changes.')
        sys.exit(1)


class RemoteDeployment(object):

    def __init__(self, environment):
        self.environment = environment

        self.upstream = cmd('hg show paths')[0].split('\n')[0].strip()
        assert self.upstream.startswith('paths.default')
        self.upstream = self.upstream.split('=')[1]

        self.repository_root = subprocess.check_output(['hg', 'root']).strip()
        self.deployment_base = os.path.relpath(
            self.environment.base_dir, self.repository_root)
        assert (self.deployment_base == '.' or
                self.deployment_base[0] not in ['.', '/'])

    def __call__(self):
        remotes = {}
        for host in self.environment.hosts.values():
            remote = RemoteHost(host, self)
            remotes[host] = remote
            remote.connect()

        # Bootstrap and get channel to batou environment
        for remote in remotes.values():
            remote.start()

        for root in self.environment.roots_in_order():
            remote = remotes[root.host]
            remote.deploy_component(root)

        for remote in remotes.values():
            remote.gateway.exit()


class RPCWrapper(object):

    def __init__(self, host):
        self.host = host

    def __getattr__(self, name):
        def call(*args, **kw):
            logger.debug('rpc {}: {}(*{}, **{})'.format
                         (self.host.host.fqdn, name, args, kw))
            self.host.channel.send((name, args, kw))
            result = self.host.channel.receive()
            logger.debug('result: {}'.format(result))
            try:
                result[0]
            except TypeError:
                pass
            else:
                if result[0] == 'batou-remote-core-error':
                    logger.error(result[1])
                    raise RuntimeError('Remote exception encountered.')
            return result
        return call


class RemoteHost(object):

    gateway = None

    def __init__(self, host, deployment):
        self.host = host
        self.deployment = deployment
        self.rpc = RPCWrapper(self)

    def connect(self, interpreter='python2.7'):
        if not self.gateway:
            logger.info('{}: connecting'.format(self.host.fqdn))
        else:
            logger.info('{}: reconnecting'.format(self.host.fqdn))
            self.gateway.exit()

        self.gateway = execnet.makegateway(
            "ssh={}//python=sudo -u {} {}".format(
                self.host.fqdn,
                self.deployment.environment.service_user,
                interpreter))
        self.channel = self.gateway.remote_exec(remote_core)

    def start(self):
        logger.info('{}: bootstrapping'.format(self.host.fqdn))
        self.rpc.lock()

        remote_base, remote_id = self.rpc.update_code(
            upstream=self.deployment.upstream)
        # XXX safety-belt: compare id to local repository

        self.remote_base = os.path.join(
            remote_base, self.deployment.deployment_base)

        # XXX send requirements file over.
        self.rpc.build_batou()

        # Now, replace the basic interpreter connection, with a "real" one that
        # has all our dependencies installed.
        self.connect(self.remote_base + '/bin/py')

        self.rpc.setup_deployment(
            self.deployment.deployment_base,
            self.deployment.environment.name,
            self.host.fqdn,
            self.deployment.environment.overrides)

    def deploy_component(self, component):
        logger.info('Deploying {}/{}'.format(self.host.fqdn, component.name))
        self.rpc.deploy(component.name)
