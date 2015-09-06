from .environment import Environment
from .utils import locked, self_id
from .utils import notify
from batou import DeploymentError, ConfigurationError, SilentConfigurationError
from batou._output import output, TerminalBackend
import sys


class Deployment(object):

    _upstream = None

    def __init__(self, environment, platform, timeout, dirty, fast):
        self.environment = environment
        self.platform = platform
        self.timeout = timeout
        self.dirty = dirty
        self.fast = fast

    def load(self):
        output.section("Preparing")

        output.step("main",
                    "Loading environment `{}`...".format(self.environment))

        self.environment = Environment(
            self.environment, self.timeout, self.platform)
        self.environment.deployment = self
        self.environment.load()

        # This is located here to avoid duplicating the verification check
        # when loading the repository on the remote environment object.
        output.step("main", "Verifying repository ...")
        self.environment.repository.verify()

        output.step("main", "Loading secrets ...")
        self.environment.load_secrets()

    def connect(self):
        output.section("Connecting")

        self.environment.prepare_connect()

        for i, host in enumerate(self.environment.hosts.values(), 1):
            output.step(host.name, "Connecting via {} ({}/{})".format(
                        self.environment.connect_method, i,
                        len(self.environment.hosts)))
            host.connect()
            host.start()

    def deploy(self):
        output.section("Deploying")

        # Pick a reference remote (the last we initialised) that will pass us
        # the order we should be deploying components in.
        reference_node = self.environment.hosts.values()[0]

        for host, component in reference_node.roots_in_order():
            output.step(
                host, "Deploying component {} ...".format(component))
            host = self.environment.hosts[host]
            host.deploy_component(component)

    def disconnect(self):
        output.step("main", "Disconnecting from nodes ...", debug=True)
        for node in self.environment.hosts.values():
            node.disconnect()


def main(environment, platform, timeout, dirty, fast):
    output.backend = TerminalBackend()
    output.line(self_id())
    with locked('.batou-lock'):
        try:
            deployment = Deployment(
                environment, platform, timeout, dirty, fast)
            deployment.load()
            deployment.connect()
            deployment.deploy()
            deployment.disconnect()
        except ConfigurationError as e:
            if e not in deployment.environment.exceptions:
                deployment.environment.exceptions.append(e)
            # Report on why configuration failed.
            for exception in deployment.environment.exceptions:
                if isinstance(e, SilentConfigurationError):
                    continue
                exception.report()
            output.section("{} ERRORS - CONFIGURATION FAILED".format(
                           len(deployment.environment.exceptions)), red=True)
            notify('Configuration failed',
                   'batou failed to configure the environment. '
                   'Check your console for details.')
            sys.exit(1)
        except DeploymentError as e:
            e.report()
            notify('Deployment failed',
                   '{} encountered an error.'.format(environment))
            output.section("DEPLOYMENT FAILED", red=True)
            sys.exit(1)
        except Exception:
            # An unexpected exception happened. Bad.
            output.error("Unexpected exception", exc_info=sys.exc_info())
            output.section("DEPLOYMENT FAILED", red=True)
            notify('Deployment failed', '')
            sys.exit(1)
        else:
            output.section("DEPLOYMENT FINISHED", green=True)
            notify('Deployment finished',
                   'Successfully deployed {}.'.format(environment))
