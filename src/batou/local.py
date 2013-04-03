from .service import ServiceConfig
from .utils import notify, locked, MultiFile, input, CycleError
import pprint
import argparse
import sys
import logging
import getpass


class LocalDeploymentMode(object):

    def __init__(self, environment, hostname):
        self.environment = environment
        self.hostname = hostname


class AutoMode(LocalDeploymentMode):

    def __call__(self):
        self.environment.acquire_passphrase(
            '{}/.batou-passphrase'.format(self.environment.service.base))
        try:
            self.environment.configure()
        except CycleError, e:
            print 'Detected cycle:'
            pprint.pprint(e.args[0])
            raise
        host = self.environment.get_host(self.hostname)
        for component in self.environment.get_sorted_components():
            if component.host is not host:
                continue
            component.deploy()


class BatchMode(LocalDeploymentMode):

    output = sys.stdout

    def input(self):
        return input('> ')

    def __call__(self):
        while True:
            try:
                command = self.input()
            except EOFError:
                break
            if not command:
                continue
            command = command.split(' ', 1)
            command, args = command[0], command[1:]
            cmd = getattr(self, 'cmd_{}'.format(command), None)
            if cmd is None:
                continue
            try:
                cmd(*args)
            except Exception:
                self.output.write('ERROR\n')
                self.output.flush()
            else:
                self.output.write('OK\n')
                self.output.flush()

    def cmd_configure(self, passphrase=None):
        self.environment.configure(passphrase)
        self.host = self.environment.get_host(self.hostname)

    def cmd_deploy(self, component):
        self.host[component].deploy()


def main():
    parser = argparse.ArgumentParser(
        description=u'Deploy components locally.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x: x.replace('.cfg', ''))
    parser.add_argument(
        'hostname', help='Host to deploy.')
    parser.add_argument(
        '--platform', default=None,
        help='Alternative platform to choose. Empty for no platform.')
    parser.add_argument(
        '-b', '--batch', action='store_true',
        help='Batch mode - read component names to deploy from STDIN.')
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='Enable debug mode. Logs stdout to `batou-debug-log`.')
    args = parser.parse_args()
    mode = BatchMode if args.batch else AutoMode


    level = logging.INFO

    if args.debug:
        log = open('batou-debug-log', 'a+')
        sys.stdout = MultiFile([sys.stdout, log])
        level = logging.DEBUG

    logging.basicConfig(stream=sys.stdout, level=level, format='%(message)s')


    with locked('.batou-lock'):
        config = ServiceConfig('.', [args.environment])
        config.platform = args.platform
        config.scan()
        try:
            environment = config.service.environments[args.environment]
        except KeyError:
            known = ', '.join(sorted(config.existing_environments))
            parser.error('environment "{}" unknown.\nKnown environments: {}'
                         .format(args.environment, known))
        try:
            mode(environment, args.hostname)()
        except:
            notify('Deployment failed',
                   '{}:{} encountered an error.'.format(
                       environment.name, args.hostname))
            raise
        else:
            notify('Deployment finished',
                   '{}:{} was deployed successfully.'.format(
                       environment.name, args.hostname))
