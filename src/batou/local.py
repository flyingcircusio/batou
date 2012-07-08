from .service import ServiceConfig
from .utils import notify, locked
import argparse
import sys
import logging


def auto_mode(environment, host):
    for component in environment.ordered_components:
        if component.host is not host:
            continue
        component.deploy()


def input(prompt):
    print prompt
    sys.stdout.flush()
    return raw_input()


def batch_mode(environment, host):
    while True:
        try:
            component = input('> ')
        except EOFError:
            break
        if not component:
            continue
        try:
            host[component].deploy()
        except Exception:
            print "ERROR"
        else:
            print "OK"


def main():
    parser = argparse.ArgumentParser(
        description=u'Deploy components locally.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x:x.replace('.cfg', ''))
    parser.add_argument(
        'hostname', help='Host to deploy.')
    parser.add_argument(
        '--platform', default=None,
        help='Alternative platform to choose. Empty for no platform.')
    parser.add_argument(
        '-b', '--batch', action='store_true',
        help='Batch mode - read component names to deploy from STDIN.')
    args = parser.parse_args()
    deploy = batch_mode if args.batch else auto_mode

    logging.basicConfig(stream=sys.stdout, level=-1000, format='%(message)s')

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
        environment.configure()
        host = environment.get_host(args.hostname)
        deploy(environment, host)
        notify('Deployment finished',
               '{}:{} was deployed successfully.'.format(
                   environment.name, host.name))
