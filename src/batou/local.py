from .environment import Environment
from .utils import notify, locked, CmdExecutionError
from batou import NonConvergingWorkingSet
import logging
import sys


logger = logging.getLogger(__name__)


def main(environment, hostname, platform, timeout):
    with locked('.batou-lock'):
        try:
            environment = Environment(environment)
            environment.load()
            if timeout is not None:
                environment.timeout = timeout
            if platform is not None:
                environment.platform = platform
            environment.load_secrets()
            environment.configure()
            for root in environment.roots_in_order(host=hostname):
                root.component.deploy()
        except (CmdExecutionError, NonConvergingWorkingSet):
            logger.error('', exc_info=True)
            notify('Deployment failed',
                   '{}:{} encountered an error.'.format(
                       environment.name, hostname))
            sys.exit(1)
        except Exception:
            logger.error('', exc_info=True)
            notify('Deployment failed',
                   '{}:{} encountered an error.'.format(
                       environment.name, hostname))
            sys.exit(1)
        else:
            notify('Deployment finished',
                   '{}:{} was deployed successfully.'.format(
                       environment.name, hostname))
