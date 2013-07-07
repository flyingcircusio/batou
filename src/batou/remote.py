from . import remote_core
from .log import setup_logging
from .secrets import add_secrets_to_environment_override
from .service import ServiceConfig
from .utils import notify, cmd
import argparse
import execnet
import json
import logging
import multiprocessing.pool
import os
import os.path
import re
import subprocess
import sys
import tempfile


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

    config = ServiceConfig('.', [args.environment])
    config.scan()
    if args.environment not in config.service.environments:
        known = ', '.join(sorted(config.existing_environments))
        logger.error('Environment "{}" unknown.\nKnown environments: {}'
                     .format(args.environment, known))
        sys.exit(1)

    environment = config.service.environments[args.environment]
    add_secrets_to_environment_override(environment)
    environment.configure()

    deployment = RemoteDeployment(environment)
    deployment()

    notify('Deployment finished',
           '{} was deployed successfully.'.format(environment.name))


class RemoteDeployment(object):

    def __init__(self, environment):
        self.environment = environment

        self.repository_root = subprocess.check_output(['hg', 'root']).strip()
        self.service_base = os.path.relpath(
                self.environment.service.base,
                self.repository_root)
        assert self.service_base[0] not in ['.', '/']

    def __call__(self):
        remotes = {}
        for host in self.environment.hosts.values():
            remote = RemoteHost(host, self)
            remotes[host] = remote
            remote.connect()

        # Bootstrap and get channel to batou environment
        for remote in remotes.values():
            remote.start()

        logger.info('Updating remote working copies... ')
        for remote in remotes.values():
            remote.update_working_copy()

        #for component in self.environment.get_sorted_components():
        #    remote = remotes[component.host]
        #    remote.deploy_component(component)

        for remote in remotes.values():
            remote.gateway.exit()



class RemoteHost(object):

    def __init__(self, host, deployment):
        self.host = host
        self.deployment = deployment

    def connect(self):
        logger.info('{}: connecting'.format(self.host.fqdn))
        self.gateway = execnet.makegateway(
            "ssh={}//python=sudo -u test2 python2.7".format(self.host.fqdn))
        self.mainloop = self.gateway.remote_exec(remote_core)

    def start(self):
        # XXX Acquire locks!

        # TODO make choice of data transfer flexible.
        self.mainloop.send('update_code')

        upstream = cmd('hg show paths')[0].split('\n')[0].strip()
        assert upstream.startswith('paths.default')
        upstream = upstream.split('=')[1]
        # Tell remote to update from this upstream URL
        self.mainloop.send(upstream)
        assert self.mainloop.receive() == 'updated'

        # XXX safety-belt: ensure clean working copy
        # XXX safety-belt: ensure no outgoing changes
        # XXX safety-belt: compare id to local repository
        remote_base = self.mainloop.receive()
        self.remote_base = os.path.join(
            remote_base, self.deployment.service_base)
        id = self.mainloop.receive()

        self.mainloop.send('build_batou')
        self.mainloop.send(self.deployment.service_base)

        result = self.mainloop.receive()
        assert result == 'OK'

        # Now, replace the basic interpreter connection, with a "real" one that
        # has all our dependencies installed.
        self.gateway.exit()

        self.gateway = execnet.makegateway(
            "ssh={}//python=sudo -u test2 {}/bin/py".format(
                self.host.fqdn, self.remote_base))
        self.mainloop = self.gateway.remote_exec(remote_core)

    def bootstrap(self):
        """Ensure that the batou and project code base is current."""
        return
        self.batou = self.cmd(
            'bin/batou-local --batch {} {}'.format(
                self.deployment.environment.name, self.host.fqdn),
            interactive=True)
        for root in self.host.components:
            root.component.remote_bootstrap(self)
        self._wait_for_remote_ready()
        overrides_file = '{}/overrides.json'.format(bouncedir)
        json.dump(self.deployment.environment.overrides,
                  self.sftp.open(overrides_file, 'w'))
        self.remote_cmd('load_overrides {}'.format(overrides_file))
        self.sftp.remove(overrides_file)
        self.remote_cmd('configure')

    def deploy_component(self, component):
        logger.info('Deploying {}/{}'.format(self.host.fqdn, component.name))
        self.remote_cmd('deploy {}'.format(component.name))
