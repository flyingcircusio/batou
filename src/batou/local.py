from .secrets import add_secrets_to_environment_override
from .service import ServiceConfig
from .utils import notify, locked, MultiFile, CycleError
import argparse
import logging
import pprint
import sys


class LocalDeployment(object):

    def __init__(self, environment, hostname):
        self.environment = environment
        self.hostname = hostname

    def __call__(self):
        add_secrets_to_environment_override(self.environment)
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
        '-d', '--debug', action='store_true',
        help='Enable debug mode. Logs stdout to `batou-debug-log`.')
    args = parser.parse_args()

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
            LocalDeployment(environment, args.hostname)()
        except:
            notify('Deployment failed',
                   '{}:{} encountered an error.'.format(
                       environment.name, args.hostname))
            raise
        else:
            notify('Deployment finished',
                   '{}:{} was deployed successfully.'.format(
                       environment.name, args.hostname))
