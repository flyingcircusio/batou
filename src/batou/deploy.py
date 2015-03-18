from .environment import Environment
from .utils import notify, locked, self_id
from batou import DeploymentError, ConfigurationError
from batou.output import output
import sys


def main(environment, platform, timeout, dirty):
    output.line(self_id())
    with locked('.batou-lock'):
        try:
            output.section("Configuration")
            output.step("main",
                        "Loading environment `{}`...".format(environment))
            environment = Environment(environment)
            environment.load()
            if timeout is not None:
                environment.timeout = timeout
            if platform is not None:
                environment.platform = platform
            output.step("main", "Loading secrets ...")
            environment.load_secrets()
            output.step("main", "Configuring components ...")
            environment.configure()
            output.section("Deployment")
            for root in environment.roots_in_order(host=hostname):
                output.step(root.host.name,
                            "Deploying component {}".format(root.name))
                root.component.deploy()
        except ConfigurationError as e:
            if e not in environment.exceptions:
                environment.exceptions.append(e)
            # Report on why configuration failed.
            for exception in environment.exceptions:
                exception.report()
            output.section("{} ERRORS - CONFIGURATION FAILED".format(
                           len(environment.exceptions)), red=True)
            notify('Configuration failed',
                   'batou failed to configure the environment. '
                   'Check your console for details.')
        except DeploymentError:
            # Report why a deployment failed.
            output.error('', exc_info=True)
            output.section("DEPLOYMENT FAILED", red=True)
            notify('Deployment failed',
                   '{}:{} encountered an error.'.format(
                       environment.name, hostname))
            sys.exit(1)
        except Exception:
            # An unexpected exception happened. Bad.
            output.error("Unexpected exception", exc_info=sys.exc_info())
            output.section("DEPLOYMENT FAILED", red=True)
            notify('Deployment failed', '')
            sys.exit(1)
        else:
            notify('Deployment finished',
                   '{}:{} was deployed successfully.'.format(
                       environment.name, hostname))
