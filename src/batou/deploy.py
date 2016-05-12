from .environment import Environment, MissingEnvironment
from .utils import locked, self_id
from .utils import notify
from batou import DeploymentError, ConfigurationError
from batou._output import output, TerminalBackend
import sys
import threading


class Connector(threading.Thread):

    def __init__(self, host):
        self.host = host
        self.exc_info = None
        super(Connector, self).__init__(name=host.name)

    def run(self):
        try:
            self.host.connect()
            self.host.start()
        except Exception:
            self.exc_info = sys.exc_info()

    def join(self):
        super(Connector, self).join()
        if self.exc_info:
            raise self.exc_info[0], self.exc_info[1], self.exc_info[2]


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

    def configure(self):
        output.section("Configuring first host")
        self.connections = iter(self._connections())
        self.connections.next().join()

    def _connections(self):
        self.environment.prepare_connect()
        for i, host in enumerate(self.environment.hosts.values(), 1):
            if host.ignore:
                output.step(host.name, "Connection ignored ({}/{})".format(
                    i, len(self.environment.hosts)),
                    bold=False, red=True)
                continue
            output.step(host.name, "Connecting via {} ({}/{})".format(
                        self.environment.connect_method, i,
                        len(self.environment.hosts)))
            c = Connector(host)
            c.start()
            yield c

    def connect(self):
        output.section("Connecting remaining hosts")
        # Consume the connection iterator to establish remaining connections.
        [t.join() for t in list(self.connections)]

    def deploy(self, predict_only=False):
        if predict_only:
            output.section("Predicting deployment actions")
        else:
            output.section("Deploying")

        # Pick a reference remote (the last we initialised) that will pass us
        # the order we should be deploying components in.
        reference_node = [h for h in self.environment.hosts.values()
                          if not h.ignore][0]

        for root in reference_node.roots_in_order():
            hostname, component, ignore_component = root
            host = self.environment.hosts[hostname]
            if host.ignore:
                output.step(
                    hostname,
                    "Skipping component {} ... (Host ignored)".format(
                        component), red=True)
                continue
            if ignore_component:
                output.step(
                    hostname, "Skipping component {} ... (Component ignored)".
                    format(component), red=True)
                continue

            output.step(
                hostname, "Deploying component {} ...".format(component))
            host.deploy_component(component, predict_only)

    def disconnect(self):
        output.step("main", "Disconnecting from nodes ...", debug=True)
        for node in self.environment.hosts.values():
            node.disconnect()


def main(environment, platform, timeout, dirty, fast, consistency_only,
         predict_only):
    output.backend = TerminalBackend()
    output.line(self_id())
    if consistency_only:
        ACTION = 'CONSISTENCY CHECK'
    elif predict_only:
        ACTION = 'DEPLOYMENT PREDICTION'
    else:
        ACTION = 'DEPLOYMENT'
    with locked('.batou-lock'):
        try:
            deployment = Deployment(
                environment, platform, timeout, dirty, fast)
            deployment.load()
            deployment.configure()
            if not consistency_only:
                deployment.connect()
                deployment.deploy(predict_only)
            deployment.disconnect()
        except MissingEnvironment as e:
            e.report()
            output.section("{} FAILED".format(ACTION), red=True)
            notify('{} FAILED'.format(ACTION),
                   'Configuration for {} encountered an error.'.format(
                       environment))
            sys.exit(1)
        except ConfigurationError as e:
            output.section("{} FAILED".format(ACTION), red=True)
            notify('{} FAILED'.format(ACTION),
                   'Configuration for {} encountered an error.'.format(
                       environment))
            sys.exit(1)
        except DeploymentError as e:
            e.report()
            output.section("{} FAILED".format(ACTION), red=True)
            notify('{} FAILED'.format(ACTION),
                   '{} encountered an error.'.format(environment))
            sys.exit(1)
        except Exception:
            # An unexpected exception happened. Bad.
            output.error("Unexpected exception", exc_info=sys.exc_info())
            output.section("{} FAILED".format(ACTION), red=True)
            notify('{} FAILED'.format(ACTION),
                   'Encountered an unexpected exception.')
            sys.exit(1)
        else:
            output.section('{} FINISHED'.format(ACTION), green=True)
            notify('{} SUCCEEDED'.format(ACTION), environment)
