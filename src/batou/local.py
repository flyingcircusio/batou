# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .service import ServiceConfig
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

    logging.basicConfig(stream=sys.stdout, level=-1000, format='%(message)s')

    config = ServiceConfig('.', [args.environment])
    config.platform = args.platform
    config.scan()
    environment = config.service.environments[args.environment]
    environment.configure()
    host = environment.get_host(args.hostname)
    if args.batch:
        batch_mode(environment, host)
    else:
        auto_mode(environment, host)
