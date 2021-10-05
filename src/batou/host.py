import ast
import os
import subprocess
import sys

import execnet.gateway_io
import yaml

from batou import (
    DeploymentError,
    SilentConfigurationError,
    output,
    remote_core,
)
from batou.utils import BagOfAttributes

# Keys in os.environ which get propagated to the remote side:
REMOTE_OS_ENV_KEYS = (
    'REMOTE_PDB_HOST',
    'REMOTE_PDB_PORT',
)


# Monkeypatch execnet to support 'vagrant ssh' and 'kitchen exec'.
# 'vagrant' support has been added to 'execnet' release 1.4.
def get_kitchen_ssh_connection_info(name):
    cmd = "kitchen", "diagnose", "--log-level=error", name
    info = yaml.load(subprocess.check_output(cmd))
    (instance, ) = list(info["instances"].values())
    state = instance["state_file"]
    return [
        "-o", "StrictHostKeyChecking=no",
        "-i", state["ssh_key"],
        "-p", state["port"],
        "-l", state["username"],
        state["hostname"]]  # yapf: disable


def new_ssh_args(spec):
    from execnet.gateway_io import popen_bootstrapline

    remotepython = spec.python or "python"
    if spec.type == "vagrant":
        args = ["vagrant", "ssh", spec.ssh, "--", "-C"]
    elif spec.type == "kitchen":
        # TODO: this should really use:
        #   args = ['kitchen', 'exec', spec.ssh, '-c']
        # but `exec` apparently doesn't connect stdin (yet)...
        args = ["ssh", "-C"] + get_kitchen_ssh_connection_info(spec.ssh)
    else:
        args = ["ssh", "-C"]
    if spec.ssh_config is not None:
        args.extend(["-F", str(spec.ssh_config)])
    remotecmd = '%s -c "%s"' % (remotepython, popen_bootstrapline)
    if spec.type == "vagrant" or spec.type == "kitchen":
        args.extend([remotecmd])
    else:
        args.extend([spec.ssh, remotecmd])
    return args


execnet.gateway_io.ssh_args = new_ssh_args


class RPCWrapper(object):

    def __init__(self, host):
        self.host = host

    def __getattr__(self, name):

        def call(*args, **kw):
            output.annotate(
                "rpc {}: {}(*{}, **{})".format(self.host.fqdn, name, args, kw),
                debug=True)
            self.host.channel.send((name, args, kw))
            while True:
                message = self.host.channel.receive()
                output.annotate(
                    "{}: message: {}".format(self.host.fqdn, message),
                    debug=True)
                type = message[0]
                if type == "batou-result":
                    return message[1]
                elif type == "batou-output":
                    _, output_cmd, args, kw = message
                    getattr(output, output_cmd)(*args, **kw)
                elif type == "batou-configuration-error":
                    raise SilentConfigurationError()
                elif type == "batou-deployment-error":
                    raise DeploymentError()
                elif type == "batou-unknown-error":
                    output.error(message[1])
                    raise RuntimeError(
                        "{}: Remote exception encountered.".format(
                            self.host.fqdn))
                elif type == "batou-error":
                    # Remote put out the details already.
                    raise RuntimeError(
                        "{}: Remote exception encountered.".format(
                            self.host.fqdn))
                else:
                    raise RuntimeError("{}: Unknown message type {}".format(
                        self.host.fqdn, type))

        return call


_no_value_marker = object()


class Host(object):

    service_user = None
    ignore = False
    platform = None
    _provisioner = None
    remap = False
    ignore = False

    def __init__(self, name, environment, config={}):
        # The _name attribute is the name that is given to this host in the
        # environment. The `name` property will return the true name for this
        # host in case that a mapping exists, e.g. due to a provisioner.
        self._name = name

        self.aliases = BagOfAttributes()

        self.data = {}

        self.rpc = RPCWrapper(self)
        self.environment = environment

        self.ignore = ast.literal_eval(config.get("ignore", "False"))

        self.platform = config.get("platform", environment.platform)
        self.service_user = config.get("service_user",
                                       environment.service_user)

        self.remap = ast.literal_eval(
            config.get("provision-dynamic-hostname", "False"))
        self._provisioner = config.get("provisioner")
        if self.provisioner:
            self.provisioner.configure_host(self, config)

        for key, value in list(config.items()):
            if key.startswith("data-"):
                key = key.replace("data-", "", 1)
                self.data[key] = value

    @property
    def provisioner(self):
        if self._provisioner == 'none':
            # Provisioning explicitly disabled for this host
            return
        elif not self._provisioner:
            # Default provisionier (if available)
            return self.environment.provisioners.get('default')
        return self.environment.provisioners[self._provisioner]

    # These are internal aliases to allow having an explicit name
    # for a host in the environment and then having a provisioner assign a
    # different "true" name for this host.
    @property
    def _aliases(self):
        if self._name == self.name:
            return []
        return [self._name]

    @property
    def name(self):
        if not self.remap:
            return self._name
        mapping = self.environment.hostname_mapping
        if self._name not in mapping:
            mapping[self._name] = self.provisioner.suggest_name(self._name)
        return mapping[self._name]

    @property
    def fqdn(self):
        name = self.name
        if self.environment.host_domain:
            name += "." + self.environment.host_domain
        return name

    def deploy_component(self, component, predict_only):
        self.rpc.deploy(component, predict_only)

    def root_dependencies(self):
        return self.rpc.root_dependencies()

    @property
    def components(self):
        return self.environment.components_for(self)

    def summarize(self):
        if self.provisioner:
            self.provisioner.summarize(self)


class LocalHost(Host):

    def connect(self):
        self.gateway = execnet.makegateway("popen//python={}".format(
            sys.executable))
        self.channel = self.gateway.remote_exec(remote_core)

    def start(self):
        self.rpc.lock()

        # Since we reconnected, any state on the remote side has been lost,
        # so we need to set the target directory again (which we only can
        # know about locally).
        self.rpc.setup_output(output.enable_debug)

        env = self.environment

        self.remote_repository = self.rpc.ensure_repository(
            env.target_directory, "local")

        self.remote_base = self.rpc.ensure_base(env.deployment_base)

        # XXX the cwd isn't right.
        self.rpc.setup_deployment(env.name, self.name, env.overrides,
                                  env.secret_files, env.secret_data,
                                  env._host_data(), env.timeout, env.platform)

    def disconnect(self):
        if hasattr(self, "gateway"):
            self.gateway.exit()


class RemoteHost(Host):

    gateway = None

    def connect(self, interpreter="python3"):
        if self.gateway:
            output.annotate("Disconnecting ...", debug=True)
            self.disconnect()

        output.annotate("Connecting ...", debug=True)
        # Call sudo, ensuring:
        # - no password will ever be asked (fail instead)
        # - we ensure a consistent set of environment variables
        #   irregardless of the local configuration of env_reset, etc.

        CONDITIONAL_SUDO = """\
if [ -n "$ZSH_VERSION" ]; then setopt SH_WORD_SPLIT; fi;
if [ \"$USER\" = \"{user}\" ]; then \
pre=\"\"; else pre=\"sudo -ni -u {user}\"; fi; $pre\
""".format(user=self.service_user)

        spec = "ssh={fqdn}//python={sudo} {interpreter}//type={method}".format(
            fqdn=self.fqdn,
            sudo=CONDITIONAL_SUDO,
            interpreter=interpreter,
            method=self.environment.connect_method)
        ssh_configs = [
            'ssh_config_{}'.format(self.environment.name), 'ssh_config']
        for ssh_config in ssh_configs:
            if os.path.exists(ssh_config):
                spec += "//ssh_config={}".format(ssh_config)
                break
        self.gateway = execnet.makegateway(spec)
        try:
            self.channel = self.gateway.remote_exec(remote_core)
        except IOError:
            raise RuntimeError(
                "Could not start batou on host `{}`. "
                "The output above may contain more information. ".format(
                    self.fqdn))

        output.annotate("Connected ...", debug=True)

    def start(self):
        output.step(self.name, "Bootstrapping ...", debug=True)
        self.rpc.lock()
        env = self.environment

        self.remote_repository = self.rpc.ensure_repository(
            env.target_directory, env.update_method)
        self.remote_base = self.rpc.ensure_base(env.deployment_base)

        output.step(self.name, "Updating repository ...", debug=True)
        env.repository.update(self)

        self.rpc.build_batou()

        # Now, replace the basic interpreter connection, with a "real" one
        # that has all our dependencies installed.
        #
        # XXX this requires an interesting move of detecting which appenv
        # version we have available to make this backwards compatible.
        self.connect(self.remote_base + "/appenv python")

        # Reinit after reconnect ...
        self.rpc.lock()
        self.remote_repository = self.rpc.ensure_repository(
            env.target_directory, env.update_method)
        self.remote_base = self.rpc.ensure_base(env.deployment_base)

        # Since we reconnected, any state on the remote side has been lost,
        # so we need to set the target directory again (which we only can
        # know about locally)
        self.rpc.setup_output(output.enable_debug)

        self.rpc.setup_deployment(
            env.name,
            self.name,
            env.overrides,
            env.secret_files,
            env.secret_data,
            env._host_data(),
            env.timeout,
            env.platform,
            {
                key: os.environ.get(key)
                for key in REMOTE_OS_ENV_KEYS if os.environ.get(key)},
        )

    def disconnect(self):
        if self.gateway is not None:
            self.gateway.exit()
