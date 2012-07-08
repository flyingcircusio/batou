from .service import ServiceConfig
from .utils import notify, locked, MultiFile, input
import argparse
import sys
import logging


def auto_mode(environment, hostname):
    environment.configure()
    host = environment.get_host(hostname)
    for component in environment.ordered_components:
        if component.host is not host:
            continue
        component.deploy()


class Batchmode(object):

    def __call__(self, environment, hostname):
        self.environment = environment
        self.hostname = hostname
        while True:
            try:
                command = input('> ')
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
                print "ERROR"
            else:
                print "OK"

    def cmd_set(self, args):
        component, attribute, expression = args.split(' ', 2)
        overrides = self.environment.overrides
        overrides = overrides.setdefault(component, {})
        # Make this an expression (e.g. evaluated using Jinja2)
        # so we can get real types over the wire.
        overrides[attribute] = expression

    def cmd_configure(self):
        self.environment.configure()
        self.host = self.environment.get_host(self.hostname)

    def cmd_deploy(self, component):
        self.host[component].deploy()


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
    deploy = Batchmode() if args.batch else auto_mode

    logging.basicConfig(stream=sys.stdout, level=-1000, format='%(message)s')


    log = open('/tmp/batou-ssh-log', 'a+')
    sys.stdout = MultiFile([sys.stdout, log])
    sys.stdin = MultiFile([sys.stdin, log])

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
        deploy(environment, args.hostname)
        notify('Deployment finished',
               '{}:{} was deployed successfully.'.format(
                   environment.name, args.hostname))
