import json
import os
import os.path
import pwd
import subprocess
import traceback

# Satisfy flake8 and support testing.
try:
    channel
except NameError:
    channel = None

deployment = None
environment = None
target_directory = ""
deployment_base = ""

# The output class should really live in _output. However, to support
# bootstrapping we define it here and then re-import in the _output module.


class Output(object):
    """Manage the output of various parts of batou to achieve
    consistency wrt to formatting and display.
    """

    enable_debug = False

    def __init__(self, backend):
        self.backend = backend
        self._buffer = []
        self._flushing = False

    # Helpers to allow constructing output with reordering and in a distributed
    # fashion.

    def buffer(self, cmd, *args, **kw):
        self._buffer.append((cmd, args, kw))

    def clear_buffer(self):
        self._buffer.clear()

    def flush_buffer(self):
        if self._flushing:
            return
        self._flushing = True
        for cmd, args, kw in self._buffer:
            getattr(self, cmd)(*args, **kw)
        self.clear_buffer()
        self._flushing = False

    def line(self, message, debug=False, **format):
        if debug and not self.enable_debug:
            return
        self.flush_buffer()
        self.backend.line(message, **format)

    def annotate(self, message, debug=False, **format):
        if debug and not self.enable_debug:
            return
        self.flush_buffer()
        lines = message.split("\n")
        message = "\n".join(lines)
        self.line(message, **format)

    def tabular(self, key, value, separator=": ", debug=False, **kw):
        if debug and not self.enable_debug:
            return
        self.flush_buffer()
        message = key.rjust(10) + separator + value
        self.annotate(message, **kw)

    def section(self, title, debug=False, **format):
        if debug and not self.enable_debug:
            return
        self.flush_buffer()
        _format = {"bold": True}
        _format.update(format)
        self.backend.sep("=", title, **_format)

    def sep(self, sep, title, **format):
        self.flush_buffer()
        return self.backend.sep(sep, title, **format)

    def step(self, context, message, debug=False, **format):
        if debug and not self.enable_debug:
            return
        self.flush_buffer()
        _format = {"bold": True}
        _format.update(format)
        self.line("{}: {}".format(context, message), **_format)

    def error(self, message, exc_info=None, debug=False):
        if debug and not self.enable_debug:
            return
        self.flush_buffer()
        self.step("ERROR", message, red=True)
        if exc_info:
            if self.enable_debug:
                out = traceback.format_exception(*exc_info)
            else:
                etype, value, _ = exc_info
                out = traceback.format_exception_only(etype, value)
            out = "".join(out)
            out = "      " + out.replace("\n", "\n      ") + "\n"
            self.backend.write(out, red=True)


class ChannelBackend(object):

    def __init__(self, channel):
        self.channel = channel

    def _send(self, output_cmd, *args, **kw):
        self.channel.send(("batou-output", output_cmd, args, kw))

    def line(self, message, **format):
        self._send("line", message, **format)

    def sep(self, sep, title, **format):
        self._send("sep", sep, title, **format)

    def write(self, content, **format):
        self._send("write", content, **format)


class Deployment(object):

    environment = None

    def __init__(self,
                 env_name,
                 host_name,
                 overrides,
                 secret_files,
                 secret_data,
                 host_data,
                 timeout,
                 platform,
                 os_env=None):
        self.env_name = env_name
        self.host_name = host_name
        self.overrides = overrides
        self.host_data = host_data
        self.secret_files = secret_files
        self.secret_data = secret_data
        self.timeout = timeout
        self.platform = platform
        self.os_env = os_env

    def load(self):
        from batou.environment import Environment

        if self.os_env:
            os.environ.update(self.os_env)
        self.environment = Environment(self.env_name, self.timeout,
                                       self.platform)
        self.environment.deployment = self
        self.environment.load()
        self.environment.overrides = self.overrides
        for hostname, data in self.host_data.items():
            self.environment.hosts[hostname].data.update(data)
        self.environment.secret_files = self.secret_files
        self.environment.secret_data = self.secret_data
        self.environment.configure()

    def deploy(self, root, predict_only):
        host = self.environment.get_host(self.host_name)
        root = self.environment.get_root(root, host)
        root.component.deploy(predict_only)


def lock():
    # XXX implement!
    return "OK"


class CmdError(Exception):

    def __init__(self, cmd, returncode, stdout, stderr):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def report(self):
        output.error(self.cmd)
        output.tabular("Return code", str(self.returncode), red=True)
        output.line("STDOUT", red=True)
        output.annotate(self.stdout.decode("utf-8", errors="replace"))
        output.line("STDERR", red=True)
        output.annotate(self.stderr.decode("utf-8", errors="replace"))


def cmd(c, acceptable_returncodes=[0]):
    process = subprocess.Popen(["LANG=C LC_ALL=C LANGUAGE=C {}".format(c)],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               stdin=subprocess.PIPE,
                               shell=True)
    stdout, stderr = process.communicate()
    # We do not have enough knowledge here to decode so we keep
    # stdout and stderr as byte strings for now.
    if process.returncode not in acceptable_returncodes:
        raise CmdError(c, process.returncode, stdout, stderr)
    return stdout, stderr


def ensure_repository(target, method):
    target = os.path.expanduser(target)
    global target_directory
    target_directory = target

    if not os.path.exists(target):
        os.makedirs(target)

    if method in ["hg-pull", "hg-bundle"]:
        if not os.path.exists(target + "/.hg"):
            cmd("hg init {}".format(target))
    elif method in ["git-pull", "git-bundle"]:
        if not os.path.exists(target + "/.git"):
            cmd("git init {}".format(target))
    elif method == "rsync":
        pass
    elif method == "local":
        pass
    else:
        raise RuntimeError("Unknown repository method: {}".format(method))

    return target


def ensure_base(base):
    global deployment_base
    deployment_base = os.path.join(target_directory, base)
    if not os.path.exists(deployment_base):
        os.makedirs(deployment_base)
    return deployment_base


def _hg_current_id():
    output, _ = cmd("hg id -Tjson")
    output = json.loads(output)
    return output[0]['id']


def hg_current_heads():
    target = target_directory
    os.chdir(target)
    id = _hg_current_id()
    if id == "0000000000000000000000000000000000000000":
        return [id]
    heads, _ = cmd("hg heads -Tjson")
    heads = json.loads(heads)
    return [x['node'] for x in heads]


def hg_pull_code(upstream):
    # TODO Make choice of VCS flexible
    target = target_directory
    os.chdir(target)
    # Phase 1: update working copy
    # XXX manage certificates
    cmd("hg pull {}".format(upstream))


def hg_unbundle_code():
    # TODO Make choice of VCS flexible
    # XXX does this protect us from accidental new heads?
    target = target_directory
    os.chdir(target)
    cmd("hg -y unbundle batou-bundle.hg")


def hg_update_working_copy(branch):
    cmd("hg up -C {}".format(branch))
    return _hg_current_id()


# Unbundle is only called if there actually is something to unbundle (see
# `GitBundleRepository`). Hence setting the origin inside `git_unbundle_code`
# doesn't work very well. OTOH `git_pull_code` is called regardles of the
# repository state. So default to `git-bundle`, and only change for pull.
git_origin = "batou-bundle"


def git_current_head():
    target = target_directory
    os.chdir(target)
    id, err = cmd('git rev-parse HEAD', acceptable_returncodes=[0, 128])
    id = id.strip()
    return id if b"unknown revision" not in err else None


def git_pull_code(upstream, branch):
    global git_origin
    git_origin = "batou-pull"
    target = target_directory
    os.chdir(target)
    out, err = cmd("git remote -v")
    for line in out.splitlines():
        line = line.strip()
        line = line.replace(" ", "\t")
        if not line:
            continue
        name, remote, _ = line.split("\t", 3)
        if name != git_origin:
            continue
        if remote != upstream:
            cmd("git remote remove {origin}".format(origin=git_origin))
        # The batou-pull remote is correctly configured.
        break
    else:
        cmd("git remote add {origin} {upstream}".format(
            origin=git_origin, upstream=upstream))
    cmd("git fetch batou-pull")


def git_unbundle_code():
    target = target_directory
    os.chdir(target)
    out, err = cmd("git remote -v")
    if b"batou-bundle" not in out:
        cmd("git remote add {origin} batou-bundle.git".format(
            origin=git_origin))
    cmd("git fetch {origin}".format(origin=git_origin))


def git_update_working_copy(branch):
    cmd("git reset --hard {origin}/{branch}".format(
        origin=git_origin, branch=branch))
    id, _ = cmd("git rev-parse HEAD")
    return id.strip().decode("ascii")


def build_batou():
    os.chdir(deployment_base)
    cmd("./batou --help")


def setup_deployment(*args):
    os.chdir(deployment_base)
    global deployment
    deployment = Deployment(*args)
    deployment.load()


def deploy(root, predict_only=False):
    deployment.deploy(root, predict_only)


def root_dependencies():
    deps = {}
    for item in deployment.environment.root_dependencies().items():
        (root, dependencies) = item
        key = (root.host.name, root.name)
        deps[key] = {
            "dependencies": [(r.host.name, r.name) for r in dependencies],
            "ignore": root.ignore}
    return deps


def whoami():
    return pwd.getpwuid(os.getuid()).pw_name


def setup_output(debug):
    from batou._output import output

    output.backend = ChannelBackend(channel)
    output.enable_debug = debug


class DummyException(Exception):
    # Support bootstrapping.
    pass


if __name__ == "__channelexec__":
    output = Output(ChannelBackend(channel))
    while not channel.isclosed():
        task, args, kw = channel.receive()
        # Support slow bootstrapping
        try:
            import batou
        except ImportError:
            batou = None
        try:
            result = locals()[task](*args, **kw)
            channel.send(("batou-result", result))
        except getattr(batou, "ConfigurationError",
                       DummyException) as exception:
            SilentConfigurationError = getattr(batou,
                                               "SilentConfigurationError",
                                               DummyException)
            ReportingException = getattr(batou, "ReportingException",
                                         DummyException)

            environment = deployment.environment
            if exception not in environment.exceptions:
                environment.exceptions.append(exception)

            environment.exceptions = list(
                filter(lambda e: not isinstance(e, SilentConfigurationError),
                       environment.exceptions))
            deployment.environment.exceptions.sort(key=lambda x: x.sort_key)

            for exception in deployment.environment.exceptions:
                if isinstance(exception, ReportingException):
                    output.line('')
                    exception.report()
                else:
                    output.line('')
                    output.error("Unexpected exception")
                    tb = traceback.TracebackException.from_exception(exception)
                    for line in tb.format():
                        output.line('\t' + line.strip(), red=True)

            batou.output.section(
                "{} ERRORS - CONFIGURATION FAILED".format(
                    len(deployment.environment.exceptions)),
                red=True)
            channel.send(("batou-configuration-error", None))
        except getattr(batou, "DeploymentError", DummyException) as e:
            e.report()
            channel.send(("batou-deployment-error", None))
        except Exception as e:
            # I voted for duck-typing here as we may be running in the
            # bootstrapping phase and don't have access to all classes yet.
            if hasattr(e, "report"):
                e.report()
                channel.send(("batou-error", None))
            else:
                tb = traceback.format_exc()
                channel.send(("batou-unknown-error", tb))
