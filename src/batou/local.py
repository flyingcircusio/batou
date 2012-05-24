# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .service import ServiceConfig
import argparse
import sys
import logging


def main():
    parser = argparse.ArgumentParser(
        description=u'Execute batou components locally.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x:x.replace('.cfg', ''))
    parser.add_argument(
        'hostname', help='Host to deploy.')
    parser.add_argument(
        '--platform', default=None,
        help='Alternative platform to choose. Empty for no platform.')
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stdout, level=-1000, format='%(message)s')

    config = ServiceConfig('.', [args.environment])
    config.platform = args.platform
    config.scan()
    environment = config.service.environments[args.environment]
    environment.get_host(args.hostname).deploy()
