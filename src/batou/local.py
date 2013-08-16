from .environment import Environment
from .utils import notify, locked
import logging
import sys


logger = logging.getLogger(__name__)


def main(environment, hostname, platform):
    with locked('.batou-lock'):
        try:
            environment = Environment(environment)
            environment.load()
            environment.platform = platform
            environment.load_secrets()
            environment.configure()
            for root in environment.roots_in_order(host=hostname):
                root.component.deploy()
        except Exception, e:
            logger.exception(e)
            notify('Deployment failed',
                   '{}:{} encountered an error.'.format(
                       environment, hostname))
            sys.exit(1)
        else:
            notify('Deployment finished',
                   '{}:{} was deployed successfully.'.format(
                       environment, hostname))
