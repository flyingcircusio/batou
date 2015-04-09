from . import remote_core
from .environment import Environment
from .utils import notify, cmd
from .utils import locked, self_id
from batou import DeploymentError, ConfigurationError
from batou._output import output, TerminalBackend
import execnet
import os
import os.path
import subprocess
import sys
import tempfile


# Monkeypatch execnet to support vagrant ssh. Can be removed
# with execnet release 1.4


def new_ssh_args(spec):
    from execnet.gateway_io import popen_bootstrapline
    remotepython = spec.python or 'python'
    if spec.type == 'vagrant':
        args = ['vagrant', 'ssh', spec.ssh, '--', '-C']
    else:
        args = ['ssh', '-C']
    if spec.ssh_config is not None:
        args.extend(['-F', str(spec.ssh_config)])
    remotecmd = '%s -c "%s"' % (remotepython, popen_bootstrapline)
    if spec.type == 'vagrant':
        args.extend([remotecmd])
    else:
        args.extend([spec.ssh, remotecmd])
    return args

import execnet.gateway_io
execnet.gateway_io.ssh_args = new_ssh_args


class Deployment(object):

    _upstream = None

    def __init__(self, environment, dirty, fast):
        self.environment = environment
        self.dirty = dirty
        self.fast = fast

        try:
            repository_root = subprocess.check_output(['hg', 'root']).strip()
            self.deployment_base = os.path.relpath(
                self.environment.base_dir, repository_root)
        except Exception:
            self.deployment_base = '.'
        assert (self.deployment_base == '.' or
                self.deployment_base[0] not in ['.', '/'])

    @property
    def upstream(self):
        if self._upstream is None:
            self._upstream = cmd('hg showconfig paths')[0]
            self._upstream = self._upstream.split('\n')[0].strip()
            assert self._upstream.startswith('paths.default')
            self._upstream = self.upstream.split('=')[1]
        return self._upstream

    def __call__(self):
        remotes = {}
        for i, host in enumerate(self.environment.hosts.values()):
            remote = RemoteHost(host, self)
            remotes[host] = remote
            remote.connect()

        # Bootstrap and get channel to batou environment
        for remote in remotes.values():
            remote.start()

        ref_remote = remotes.values()[0]
        roots = ref_remote.roots_in_order()

        output.section("Deployment")

        for host, component in roots:
            output.step(host,
                        "Deploying component {} ...".format(component))
            host = self.environment.hosts[host]
            remote = remotes[host]

            remote.deploy_component(component)

        output.step("main", "Disconnecting from nodes ...", debug=True)
        for remote in remotes.values():
            remote.gateway.exit()


class RPCWrapper(object):

    def __init__(self, host):
        self.host = host

    def __getattr__(self, name):
        def call(*args, **kw):
            output.annotate(
                'rpc {}: {}(*{}, **{})'.format(self.host.host.fqdn,
                                               name, args, kw),
                debug=True)
            self.host.channel.send((name, args, kw))
            while True:
                message = self.host.channel.receive()
                output.annotate('message: {}'.format(message), debug=True)
                type = message[0]
                if type == 'batou-result':
                    return message[1]
                elif type == 'batou-output':
                    _, output_cmd, args, kw = message
                    getattr(output, output_cmd)(*args, **kw)
                elif type in ['batou-unknown-error', 'batou-error']:
                    output.error(message[1])
                    raise RuntimeError('Remote exception encountered.')
                else:
                    raise RuntimeError("Unknown message type {}".format(type))
        return call


class RemoteHost(object):

    gateway = None

    def __init__(self, host, deployment):
        self.host = host
        self.deployment = deployment
        self.rpc = RPCWrapper(self)
        self.target_directory = deployment.environment.target_directory

    def connect(self, interpreter='python2.7'):
        if not self.gateway:
            output.step(self.host.name, 'Connecting ...')
        else:
            output.step(self.host.name, 'Reconnecting ...', debug=True)
            self.gateway.exit()

        if self.deployment.environment.connect_method in ['ssh', 'vagrant']:
            self._connect_ssh_vagrant(interpreter)
        elif self.deployment.environment.connect_method == 'local':
            self._connect_popen(interpreter)

    def _connect_popen(self, interpreter):
        # Support experimenting/testing with remote deployments without
        # hassling with SSH/vagrant
        self.gateway = execnet.makegateway(
            "popen//python={}".format(interpreter))
        self.target_directory = '/tmp/{}'.format(self.host.fqdn)
        self.channel = self.gateway.remote_exec(remote_core)

    def _connect_ssh_vagrant(self, interpreter):
        self.gateway = execnet.makegateway(
            "ssh={}//python={}//type={}".format(
                self.host.fqdn, interpreter,
                self.deployment.environment.connect_method))
        self.channel = self.gateway.remote_exec(remote_core)

        if self.rpc.whoami() != self.deployment.environment.service_user:
            self.gateway.exit()
            self.gateway = execnet.makegateway(
                "ssh={}//python=sudo -u {} {}//type={}".format(
                    self.host.fqdn,
                    self.deployment.environment.service_user,
                    interpreter,
                    self.deployment.environment.connect_method))
            self.channel = self.gateway.remote_exec(remote_core)

    def update_hg_bundle(self):
        heads = self.rpc.current_heads()
        if not heads:
            raise ValueError("Remote repository did not find any heads. "
                             "Can not continue creating a bundle.")
        fd, bundle_file = tempfile.mkstemp()
        os.close(fd)
        bases = ' '.join('--base {}'.format(x) for x in heads)
        cmd('hg -qy bundle {} {}'.format(bases, bundle_file),
            acceptable_returncodes=[0, 1])
        have_changes = os.stat(bundle_file).st_size > 0
        self.rpc.send_file(
            bundle_file, self.remote_repository + '/batou-bundle.hg')
        os.unlink(bundle_file)
        if have_changes:
            self.rpc.unbundle_code()

    def update_hg(self):
        env = self.deployment.environment

        if env.update_method == 'pull':
            self.rpc.pull_code(
                upstream=self.deployment.upstream)
        elif env.update_method == 'bundle':
            self.update_hg_bundle()

        remote_id = self.rpc.update_working_copy(env.branch)
        local_id, _ = cmd('hg id -i')
        if self.deployment.dirty:
            local_id = local_id.replace('+', '')
        local_id = local_id.strip()
        if remote_id != local_id:
            raise RuntimeError(
                'Working copy parents differ. Local: {} Remote: {}'.format(
                    local_id, remote_id))

        remote_id = self.rpc.update_working_copy(env.branch)
        local_id, _ = cmd('hg id -i')
        if self.deployment.dirty:
            local_id = local_id.replace('+', '')
        local_id = local_id.strip()
        if remote_id != local_id:
            raise RuntimeError(
                'Working copy parents differ. Local: {} Remote: {}'.format(
                    local_id, remote_id))

    def update_rsync(self):
        env = self.deployment.environment
        blacklist = ['.batou', 'work', '.git', '.hg', '.vagrant',
                     '.batou-lock']
        for candidate in os.listdir(env.base_dir):
            if candidate in blacklist:
                continue

            source = os.path.join(env.base_dir, candidate)
            target = os.path.join(self.remote_base, candidate)
            output.annotate("rsync source: {}".format(source), debug=True)
            output.annotate("rsync target: {}".format(target), debug=True)
            rsync = execnet.RSync(source)
            rsync.add_target(self.gateway, target)
            rsync.send()

    def start(self):
        output.step(self.host.name, 'Bootstrapping ...', debug=True)
        self.rpc.lock()
        env = self.deployment.environment

        self.remote_repository = self.rpc.ensure_repository(
            self.target_directory, env.update_method)
        self.remote_base = self.rpc.ensure_base(
            self.deployment.deployment_base)

        if env.update_method in ['pull', 'bundle']:
            self.update_hg()
        elif env.update_method == 'rsync':
            self.update_rsync()
        else:
            raise ValueError(
                'unsupported update method: {}'.format(env.update_method))

        develop = os.environ.get('BATOU_DEVELOP')
        if '://' not in develop:
            develop = os.path.abspath(develop)
        self.rpc.build_batou(self.deployment.deployment_base,
                             fast=self.deployment.fast,
                             version=os.environ.get('BATOU_VERSION'),
                             develop=develop)

        # Now, replace the basic interpreter connection, with a "real" one
        # that has all our dependencies installed.
        self.connect(self.remote_base + '/.batou/bin/python')

        # Since we reconnected, any state on the remote side has been lost,
        # so we need to set the target directory again (which we only can
        # know about locally). XXX This is quite convoluted.
        self.rpc.setup_output()

        self.rpc.ensure_repository(env.target_directory, env.update_method)

        self.rpc.setup_deployment(
            self.remote_base,
            env.name,
            self.host.fqdn,
            env.overrides)

    def deploy_component(self, component):
        self.rpc.deploy(component)

    def roots_in_order(self):
        return self.rpc.roots_in_order()


def check_clean_hg_repository():
    # Safety belt that we're acting on a clean repository.
    try:
        status, _ = cmd('hg -q stat', silent=True)
    except RuntimeError:
        output.error('Unable to check repository status. '
                     'Is there an HG repository here?')
        sys.exit(1)
    else:
        status = status.strip()
        if status.strip():
            output.error("Your repository has uncommitted changes.")
            output.annotate("""\
I am refusing to deploy in this situation as the results will be unpredictable.
Please commit and push first.
""", red=True)
            output.annotate(status, red=True)
            raise DeploymentError()
    try:
        cmd('hg -q outgoing -l 1', acceptable_returncodes=[1])
    except RuntimeError:
        output.error("""\
Your repository has outgoing changes.

I am refusing to deploy in this situation as the results will be unpredictable.
Please push first.
""")
        raise DeploymentError()


def main(environment, platform, timeout, dirty, fast):
    output.backend = TerminalBackend()
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
            if environment.update_method == 'rsync':
                pass
            elif not dirty:
                output.step("main", "Checking working directory state ...")
                check_clean_hg_repository()

            output.step("main", "Loading secrets ...")
            environment.load_secrets()
            deployment = Deployment(environment, dirty, fast)
            deployment()
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
            # XXX Report why a deployment failed.
            # output.error('', exc_info=True)
            output.section("DEPLOYMENT FAILED", red=True)
            notify('Deployment failed',
                   '{} encountered an error.'.format(environment.name))
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
                   'Successfully deployed {}.'.format(environment.name))
