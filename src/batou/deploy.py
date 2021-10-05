import asyncio
import random
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from batou import ReportingException, SilentConfigurationError
from batou._output import TerminalBackend, output

from .environment import Environment
from .utils import locked, notify, self_id


class Connector(threading.Thread):

    def __init__(self, host, sem):
        self.host = host
        self.sem = sem
        self.exc_info = None
        super(Connector, self).__init__(name=host.name)

    def run(self):
        tries = 0
        while True:
            tries += 1
            self.exc_info = None
            self.sem.acquire()
            try:
                self.host.connect()
                break
            except Exception:
                self.exc_info = sys.exc_info()
                if tries >= 3:
                    return
            finally:
                self.sem.release()
            time.sleep(random.randint(1, 2**(tries + 1)))

        try:
            self.host.start()
        except Exception:
            self.exc_info = sys.exc_info()

    def join(self):
        super(Connector, self).join()
        if self.exc_info:
            exc_type, exc_value, exc_tb = self.exc_info
            raise exc_value.with_traceback(exc_tb)


class Deployment(object):

    _upstream = None

    def __init__(self,
                 environment,
                 platform,
                 timeout,
                 dirty,
                 jobs,
                 predict_only=False,
                 provision_rebuild=False):

        self.environment = Environment(
            environment,
            timeout,
            platform,
            provision_rebuild=provision_rebuild)
        self.environment.deployment = self

        self.dirty = dirty
        self.predict_only = predict_only
        self.jobs = jobs

    def load(self):
        output.section("Preparing")

        output.step(
            "main",
            "Loading environment `{}`...".format(self.environment.name))
        self.environment.load()

        if self.jobs is not None:
            self.jobs = self.jobs
        elif self.environment.jobs is not None:
            self.jobs = int(self.environment.jobs)
        else:
            self.jobs = 1
        output.step("main", "Number of jobs: %s" % self.jobs, debug=True)

        # This is located here to avoid duplicating the verification check
        # when loading the repository on the remote environment object.
        output.step("main", "Verifying repository ...")
        self.environment.repository.verify()

        output.step("main", "Loading secrets ...")
        self.environment.load_secrets()

    def provision(self):
        if not self.environment.provisioners:
            return
        output.section("Provisioning hosts ...")
        for host in self.environment.hosts.values():
            if host.provisioner:
                output.step(
                    host.name, "Provisioning with `{}` provisioner. {}".format(
                        host.provisioner.name,
                        "(Rebuild)" if host.provisioner.rebuild else ""))
                host.provisioner.provision(host)

    def configure(self):
        output.section("Configuring model ...")
        self.connections[0].join()

    def _connections(self):
        self.environment.prepare_connect()
        hosts = sorted(self.environment.hosts)
        for i, hostname in enumerate(hosts, 1):
            host = self.environment.hosts[hostname]
            if host.ignore:
                output.step(
                    hostname,
                    "Connection ignored ({}/{})".format(
                        i, len(self.environment.hosts)),
                    bold=False,
                    red=True)
                continue
            output.step(
                hostname, "Connecting via {} ({}/{})".format(
                    self.environment.connect_method, i,
                    len(self.environment.hosts)))
            sem = threading.Semaphore(5)
            c = Connector(host, sem)
            c.start()
            yield c

    def connect(self):
        output.section("Connecting ...")
        # Consume the connection iterator to establish remaining connections.
        self.connections = list(self._connections())

    def _launch_components(self, todolist):
        for key, info in list(todolist.items()):
            if info["dependencies"]:
                continue
            del todolist[key]
            asyncio.ensure_future(self._deploy_component(key, info, todolist))

    async def _deploy_component(self, key, info, todolist):
        hostname, component = key
        host = self.environment.hosts[hostname]
        if host.ignore:
            output.step(
                hostname,
                "Skipping component {} ... (Host ignored)".format(component),
                red=True)
        elif info["ignore"]:
            output.step(
                hostname,
                "Skipping component {} ... (Component ignored)".format(
                    component),
                red=True)
        else:
            output.step(hostname,
                        "Scheduling component {} ...".format(component))
            await self.loop.run_in_executor(None, host.deploy_component,
                                            component, self.predict_only)

        # Clear dependency from todolist
        for other_component in todolist.values():
            if key in other_component["dependencies"]:
                other_component["dependencies"].remove(key)

        # Trigger start of unblocked dependencies
        self._launch_components(todolist)

    def deploy(self):
        # Wait for all connections to finish
        output.section("Waiting for remaining connections ...")
        [c.join() for c in self.connections]

        if self.predict_only:
            output.section("Predicting deployment actions")
        else:
            output.section("Deploying")

        # Pick a reference remote (the last we initialised) that will pass us
        # the order we should be deploying components in.
        reference_node = [
            h for h in list(self.environment.hosts.values())
            if not h.ignore][0]

        self.loop = asyncio.get_event_loop()
        self.taskpool = ThreadPoolExecutor(self.jobs)
        self.loop.set_default_executor(self.taskpool)
        self._launch_components(reference_node.root_dependencies())

        # asyncio.Task.all_tasks was removed in Python 3.9
        # but the replacement asyncio.all_tasks is only available
        # for Python 3.7 and upwards
        # confer https://docs.python.org/3/whatsnew/3.7.html
        # and https://docs.python.org/3.9/whatsnew/3.9.html
        if sys.version_info < (3, 7):
            all_tasks = asyncio.Task.all_tasks
        else:
            all_tasks = asyncio.all_tasks

        def get_pending():
            return {t for t in all_tasks(self.loop) if not t.done()}

        pending = get_pending()
        while pending:
            self.loop.run_until_complete(asyncio.gather(*pending))
            pending = get_pending()

    def summarize(self):
        output.section("Summary")
        for node in list(self.environment.hosts.values()):
            node.summarize()

    def disconnect(self):
        output.step("main", "Disconnecting from nodes ...", debug=True)
        for node in list(self.environment.hosts.values()):
            node.disconnect()


def main(environment, platform, timeout, dirty, consistency_only, predict_only,
         jobs, provision_rebuild):
    output.backend = TerminalBackend()
    output.line(self_id())
    STEPS = [
        'load', 'provision', 'connect', 'configure', 'deploy', 'summarize']
    if consistency_only:
        ACTION = "CONSISTENCY CHECK"
        STEPS.remove('deploy')
    elif predict_only:
        ACTION = "DEPLOYMENT PREDICTION"
    else:
        ACTION = "DEPLOYMENT"
    with locked(".batou-lock"):
        deployment = Deployment(environment, platform, timeout, dirty, jobs,
                                predict_only, provision_rebuild)
        environment = deployment.environment
        try:
            for step in STEPS:
                try:
                    getattr(deployment, step)()
                except Exception as e:
                    environment.exceptions.append(e)

                if not environment.exceptions:
                    continue

                # Note: There is a similar sorting / output routine in
                # remote_core __channelexec__. This is a bit of copy/paste
                # due to the way bootstrapping works
                environment.exceptions = list(
                    filter(
                        lambda e: not isinstance(e, SilentConfigurationError),
                        environment.exceptions))

                environment.exceptions.sort(
                    key=lambda x: getattr(x, 'sort_key', (-99, )))

                exception = ''
                for exception in environment.exceptions:
                    if isinstance(exception, ReportingException):
                        output.line('')
                        exception.report()
                    else:
                        output.line('')
                        output.error("Unexpected exception")
                        tb = traceback.TracebackException.from_exception(
                            exception)
                        for line in tb.format():
                            output.line('\t' + line.strip(), red=True)

                summary = "{} FAILED (during {})".format(ACTION, step)
                output.section(summary, red=True)

                notify(summary, str(exception))
                sys.exit(1)

        finally:
            deployment.disconnect()
        output.section("{} FINISHED".format(ACTION), green=True)
        notify("{} SUCCEEDED".format(ACTION), environment.name)
