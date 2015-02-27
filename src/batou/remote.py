from . import remote_core
from .environment import Environment
from .utils import notify, cmd
import execnet
import logging
import os
import os.path
import subprocess
import sys
import tempfile

# Monkeypatch execnet to support vagrant ssh.


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


logger = logging.getLogger('batou.remote')


def main(environment, timeout, dirty):
    environment = Environment(environment)
    environment.load()
    if timeout is not None:
        environment.timeout = timeout
    if environment.update_method == 'rsync':
        pass
    elif not dirty:
        check_clean_hg_repository()
    environment.load_secrets()

    deployment = RemoteDeployment(environment, dirty)
    try:
        deployment()
    except Exception:
        logger.error('', exc_info=True)
        sys.exit(1)
    else:
        notify('Deployment finished',
               '{} was deployed successfully.'.format(environment.name))


def check_clean_hg_repository():
    # Safety belt that we're acting on a clean repository.
    try:
        status, _ = cmd('hg -q stat', silent=True)
    except RuntimeError:
        logger.error('Unable to check repository status. '
                     'Is there an HG repository here?')
        sys.exit(1)
    else:
        status = status.strip()
        if status.strip():
            logger.error("""\
Your repository has uncommitted changes.

I am refusing to deploy in this situation as the results will be unpredictable.
Please commit and push first.
""")
            logger.error(status)
            sys.exit(1)

    try:
        cmd('hg -q outgoing -l 1', acceptable_returncodes=[1])
    except RuntimeError:
        logger.error("""\
Your repository has outgoing changes.

I am refusing to deploy in this situation as the results will be unpredictable.
Please push first.
""")
        sys.exit(1)


class RemoteDeployment(object):

    def __init__(self, environment, dirty):
        self.environment = environment
        self.dirty = dirty

        self.upstream = cmd('hg showconfig paths')[0].split('\n')[0].strip()
        assert self.upstream.startswith('paths.default')
        self.upstream = self.upstream.split('=')[1]

        self.repository_root = subprocess.check_output(['hg', 'root']).strip()
        self.deployment_base = os.path.relpath(
            self.environment.base_dir, self.repository_root)
        assert (self.deployment_base == '.' or
                self.deployment_base[0] not in ['.', '/'])

    def __call__(self):
        remotes = {}
        for host in self.environment.hosts.values():
            remote = RemoteHost(host, self)
            remotes[host] = remote
            remote.connect()

        # Bootstrap and get channel to batou environment
        for remote in remotes.values():
            remote.start()

        ref_remote = remotes.values()[0]
        roots = ref_remote.roots_in_order()

        for host, component in roots:
            host = self.environment.hosts[host]
            remote = remotes[host]
            remote.deploy_component(component)

        for remote in remotes.values():
            remote.gateway.exit()


class RPCWrapper(object):

    def __init__(self, host):
        self.host = host

    def __getattr__(self, name):
        def call(*args, **kw):
            logger.debug('rpc {}: {}(*{}, **{})'.format
                         (self.host.host.fqdn, name, args, kw))
            self.host.channel.send((name, args, kw))
            result = self.host.channel.receive()
            logger.debug('result: {}'.format(result))
            try:
                result[0]
            except (TypeError, IndexError):
                pass
            else:
                if result[0] == 'batou-remote-core-error':
                    logger.error(result[1])
                    raise RuntimeError('Remote exception encountered.')
            return result
        return call

    def send_file(self, local, remote):
        self.host.channel.send(('send_file', [remote], {}))
        with open(local, 'r') as f:
            while True:
                data = f.read(64*1024)
                if not data:
                    self.host.channel.send(('finish', ''))
                    break
                else:
                    self.host.channel.send((None, data))
        result = self.host.channel.receive()
        logger.debug('result: {}'.format(result))
        try:
            result[0]
        except TypeError:
            pass
        else:
            if result[0] == 'batou-remote-core-error':
                logger.error(result[1])
                raise RuntimeError('Remote exception encountered.')
        assert result == 'OK'


class RemoteHost(object):

    gateway = None

    def __init__(self, host, deployment):
        self.host = host
        self.deployment = deployment
        self.rpc = RPCWrapper(self)

    def connect(self, interpreter='python2.7'):
        if not self.gateway:
            logger.info('{}: connecting'.format(self.host.fqdn))
        else:
            logger.info('{}: reconnecting'.format(self.host.fqdn))
            self.gateway.exit()

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
        blacklist = ['.batou', 'work', '.git', '.hg', '.vagrant']
        for source in os.listdir(env.base_dir):
            if source in blacklist:
                continue
            rsync = execnet.RSync(os.path.join(env.base_dir, source))
            rsync.add_target(self.gateway,
                             os.path.join(self.remote_base, source))
            rsync.send()

    def start(self):
        logger.info('{}: bootstrapping'.format(self.host.fqdn))
        self.rpc.lock()
        env = self.deployment.environment

        self.remote_repository = self.rpc.ensure_repository(
            env.target_directory, env.update_method)
        self.remote_base = os.path.join(
            self.remote_repository, self.deployment.deployment_base)

        if env.update_method in ['pull', 'bundle']:
            self.update_hg()
        elif env.update_method == 'rsync':
            self.update_rsync()
        else:
            raise ValueError(
                'unsupported update method: {}'.format(env.update_method))

        self.rpc.build_batou(self.deployment.deployment_base)

        # Now, replace the basic interpreter connection, with a "real" one that
        # has all our dependencies installed.
        self.connect(self.remote_base + '/.batou/bin/python')

        # Since we reconnected, any state on the remote side has been lost, so
        # we need to set the target directory again (which we only can know
        # about locally). XXX This is quite convoluted.
        self.rpc.ensure_repository(env.target_directory, env.update_method)

        self.rpc.setup_deployment(
            self.deployment.deployment_base,
            env.name,
            self.host.fqdn,
            env.overrides)

    def deploy_component(self, component):
        logger.info('Deploying {}/{}'.format(self.host.fqdn, component))
        self.rpc.deploy(component)

    def roots_in_order(self):
        return self.rpc.roots_in_order()
