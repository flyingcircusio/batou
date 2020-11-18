from batou import output, DeploymentError, ConfigurationError
from batou import remote_core
import execnet.gateway_io
import os
import subprocess
import sys
import yaml

# Monkeypatch execnet to support 'vagrant ssh' and 'kitchen exec'.
# 'vagrant' support has been added to 'execnet' release 1.4.


def get_kitchen_ssh_connection_info(name):
    cmd = 'kitchen', 'diagnose', '--log-level=error', name
    info = yaml.load(subprocess.check_output(cmd))
    (instance,) = list(info['instances'].values())
    state = instance['state_file']
    return [
        '-o', 'StrictHostKeyChecking=no',
        '-i', state['ssh_key'],
        '-p', state['port'],
        '-l', state['username'],
        state['hostname'],
    ]


def new_ssh_args(spec):
    from execnet.gateway_io import popen_bootstrapline
    remotepython = spec.python or 'python'
    if spec.type == 'vagrant':
        args = ['vagrant', 'ssh', spec.ssh, '--', '-C']
    elif spec.type == 'kitchen':
        # TODO: this should really use:
        #   args = ['kitchen', 'exec', spec.ssh, '-c']
        # but `exec` apparently doesn't connect stdin (yet)...
        args = ['ssh', '-C'] + get_kitchen_ssh_connection_info(spec.ssh)
    else:
        args = ['ssh', '-C']
    if spec.ssh_config is not None:
        args.extend(['-F', str(spec.ssh_config)])
    remotecmd = '%s -c "%s"' % (remotepython, popen_bootstrapline)
    if spec.type == 'vagrant' or spec.type == 'kitchen':
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
                'rpc {}: {}(*{}, **{})'.format(self.host.fqdn, name, args, kw),
                debug=True)
            self.host.channel.send((name, args, kw))
            while True:
                message = self.host.channel.receive()
                output.annotate('{}: message: {}'.format(
                    self.host.fqdn, message), debug=True)
                type = message[0]
                if type == 'batou-result':
                    return message[1]
                elif type == 'batou-output':
                    _, output_cmd, args, kw = message
                    getattr(output, output_cmd)(*args, **kw)
                elif type == 'batou-configuration-error':
                    raise ConfigurationError(None)
                elif type == 'batou-deployment-error':
                    raise DeploymentError()
                elif type == 'batou-unknown-error':
                    output.error(message[1])
                    raise RuntimeError(
                        '{}: Remote exception encountered.'.format(
                            self.host.fqdn))
                elif type == 'batou-error':
                    # Remote put out the details already.
                    raise RuntimeError(
                        '{}: Remote exception encountered.'.format(
                            self.host.fqdn))
                else:
                    raise RuntimeError(
                        "{}: Unknown message type {}".format(
                            self.host.fqdn, type))
        return call


_no_value_marker = object()


class Host(object):

    service_user = None
    ignore = False
    platform = None

    def __init__(self, fqdn, environment):
        self.fqdn = fqdn
        self.name = self.fqdn.split('.')[0]
        self.data = {}

        self.rpc = RPCWrapper(self)
        self.environment = environment

    def deploy_component(self, component, predict_only):
        self.rpc.deploy(component, predict_only)

    def root_dependencies(self):
        return self.rpc.root_dependencies()

    @property
    def components(self):
        return self.environment.components_for(self)


class LocalHost(Host):

    def connect(self):
        self.gateway = execnet.makegateway(
            "popen//python={}".format(sys.executable))
        self.channel = self.gateway.remote_exec(remote_core)

    def start(self):
        self.rpc.lock()

        # Since we reconnected, any state on the remote side has been lost,
        # so we need to set the target directory again (which we only can
        # know about locally).
        self.rpc.setup_output()

        env = self.environment

        self.remote_repository = self.rpc.ensure_repository(
            env.target_directory, 'local')

        self.remote_base = self.rpc.ensure_base(
            env.deployment_base)

        # XXX the cwd isn't right.
        self.rpc.setup_deployment(
            env.name, self.fqdn,
            env.overrides, env._host_data(),
            env.deployment.timeout, env.deployment.platform)

    def disconnect(self):
        if hasattr(self, 'gateway'):
            self.gateway.exit()


class RemoteHost(Host):

    gateway = None

    def connect(self, interpreter='python3'):
        if self.gateway:
            output.annotate('Disconnecting ...', debug=True)
            self.disconnect()

        output.annotate('Connecting ...', debug=True)
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
        if os.path.exists('ssh_config'):
            spec += '//ssh_config=ssh_config'
        self.gateway = execnet.makegateway(spec)
        self.channel = self.gateway.remote_exec(remote_core)

        output.annotate('Connected ...', debug=True)

    def start(self):
        output.step(self.name, 'Bootstrapping ...', debug=True)
        self.rpc.lock()
        env = self.environment

        self.remote_repository = self.rpc.ensure_repository(
            env.target_directory, env.update_method)
        self.remote_base = self.rpc.ensure_base(
            env.deployment_base)

        output.step(self.name, 'Updating repository ...', debug=True)
        env.repository.update(self)

        self.rpc.build_batou()

        # Now, replace the basic interpreter connection, with a "real" one
        # that has all our dependencies installed.
        self.connect(self.remote_base + '/batou appenv-python')

        # Reinit after reconnect ...
        self.rpc.lock()
        self.remote_repository = self.rpc.ensure_repository(
            env.target_directory, env.update_method)
        self.remote_base = self.rpc.ensure_base(
            env.deployment_base)

        # Since we reconnected, any state on the remote side has been lost,
        # so we need to set the target directory again (which we only can
        # know about locally)
        self.rpc.setup_output()

        self.rpc.setup_deployment(
            env.name,
            self.fqdn,
            env.overrides, env._host_data(),
            env.deployment.timeout, env.deployment.platform)

    def disconnect(self):
        if self.gateway is not None:
            self.gateway.exit()
