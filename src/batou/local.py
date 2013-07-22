from .utils import notify, locked
from .environment import Environment
import argparse
import logging
import sys


def main():
    parser = argparse.ArgumentParser(
        description=u'Deploy components locally.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x: x.replace('.cfg', ''))
    parser.add_argument(
        'hostname', help='Host to deploy.')
    parser.add_argument(
        '-p', '--platform', default=None,
        help='Alternative platform to choose. Empty for no platform.')
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='Enable debug mode.')
    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(stream=sys.stdout, level=level, format='%(message)s')

    with locked('.batou-lock'):
        try:
            environment = Environment(args.environment)
            environment.load()
            environment.platform = args.platform
            environment.load_secrets()
            environment.configure()
            for root in environment.roots_in_order(host=args.hostname):
                root.deploy()
        except:
            notify('Deployment failed',
                   '{}:{} encountered an error.'.format(
                       args.environment, args.hostname))
            raise
        else:
            notify('Deployment finished',
                   '{}:{} was deployed successfully.'.format(
                       environment.name, args.hostname))
