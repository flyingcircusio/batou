from . import remote_core
from .log import setup_logging
from .secrets import add_secrets_to_environment_override
from .service import ServiceConfig
from .utils import notify, cmd
import argparse
import execnet
import logging
import os
import os.path
import subprocess
import sys


logger = logging.getLogger('batou.remote')


def main():
    parser = argparse.ArgumentParser(
        description=u'Deploy a batou environment remotely.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x: x.replace('.cfg', ''))
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='Enable debug mode.')
    args = parser.parse_args()

    setup_logging(
        ['batou'],
        logging.DEBUG if args.debug else logging.INFO)

    # XXX See #12602. Put safety belt back again.

    environment = Environment(args.environment)
    environment.load_secrets()
    environment.configure()

    deployment = RemoteDeployment(environment)
    try:
        deployment()
    except RuntimeError, e:
        logger.error('\n'.join(str(x) for x in e.args))
    except Exception, e:
        logger.exception(e)
    else:
        notify('Deployment finished',
               '{} was deployed successfully.'.format(environment.name))


class RemoteDeployment(object):

    def __init__(self, environment):
        self.environment = environment

        self.upstream = cmd('hg show paths')[0].split('\n')[0].strip()
        assert self.upstream.startswith('paths.default')
        self.upstream = self.upstream.split('=')[1]

        self.repository_root = subprocess.check_output(['hg', 'root']).strip()
        self.deployment_base = os.path.relpath(
            self.environment.base, self.repository_root)
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
            remote.deploy(root)

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
                    class_, mod, args = result[1:]
                    mod = __import__(mod)
                    class_ = getattr(mod, class_)
                    raise class_(*args)
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
                self.host.environment.service_user,
                interpreter))
        self.channel = self.gateway.remote_exec(remote_core)

    def start(self):
        logger.info('{}: bootstrapping'.format(self.host.fqdn))
        self.rpc.lock()

        # XXX safety-belt: ensure clean working copy
        # XXX safety-belt: ensure no outgoing changes
        # XXX safety-belt: compare id to local repository
        remote_base, remote_id = self.rpc.update_code(
            upstream=self.deployment.upstream)

        self.remote_base = os.path.join(
            remote_base, self.deployment.service_base)

        self.rpc.build_batou(self.deployment.service_base)

        # Now, replace the basic interpreter connection, with a "real" one that
        # has all our dependencies installed.
        self.connect(self.remote_base + '/bin/py')

        self.rpc.setup_service(
            self.deployment.service_base,
            self.deployment.environment.name,
            self.host.fqdn,
            self.deployment.environment.overrides)

    def deploy_component(self, component):
        logger.info('Deploying {}/{}'.format(self.host.fqdn, component.name))
        self.rpc.deploy_component(component.name)
