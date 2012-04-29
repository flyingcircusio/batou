# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .service import ServiceConfig
import argparse
import locale


def main():
    locale.setlocale(locale.LC_ALL, '')
    parser = argparse.ArgumentParser(
        description=u'Execute batou components locally.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x:x.replace('.cfg', ''))
    parser.add_argument(
        'hostname', help='Host to deploy.')
    args = parser.parse_args()

    config = ServiceConfig('.', [args.environment])
    config.scan()
    environment = config.service.environments[args.environment]
    config.configure_components(environment)
    environment.get_host(args.hostname).deploy()
