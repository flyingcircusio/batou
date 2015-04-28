from .environment import Environment
from .utils import locked, self_id
from .utils import notify
from batou import DeploymentError, ConfigurationError
from batou._output import output, TerminalBackend
from batou.repository import detect_repository
import os.path
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
        self.environment.load()

        # Verify the repository
        output.step("main", "Verifying repository ...")
        self.repository = detect_repository(self.environment)
        self.repository.verify()

        # The deployment base is the path relative to the
        # repository where batou is located (with ./batou,
        # ./environments, and ./components)
        self.deployment_base = os.path.relpath(self.environment.base_dir,
                                               self.repository)

        output.step("main", "Loading secrets ...")
        self.environment.load_secrets()

    def connect(self):
        output.section("Connecting")

        for i, host in enumerate(self.environment.hosts.values(), 1):
            output.step(host.name, "Connecting ({}/{})".format(
                        i, len(self.environment.hosts)))
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
            notify('Deployment failed',
                   '{} encountered an error.'.format(environment))
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
