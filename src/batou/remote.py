from .utils import notify
from .service import ServiceConfig
from paramiko import AutoAddPolicy
from paramiko.client import SSHClient
import argparse
import logging
import multiprocessing.pool
import os
import os.path
import re
import subprocess
import sys
import time


logger = logging.getLogger('batou.remote')


def main():
    parser = argparse.ArgumentParser(
        description=u'Deploy a batou environment remotely.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x: x.replace('.cfg', ''))
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='Enable debug mode.')
    parser.add_argument(
        '-D', '--dirty', action='store_true',
        help='Allow deploying dirty working copies.')
    parser.add_argument(
        '--ssh-user', default=None,
        help='User to connect to via SSH')
    args = parser.parse_args()

    if args.debug:
        loggers = ['batou', 'ssh']
        log_level = logging.DEBUG
    else:
        loggers = ['batou']
        log_level = logging.INFO

    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    for log in loggers:
        log = logging.getLogger(log)
        log.setLevel(log_level)
        log.addHandler(handler)

    # Verify that we have a repository and no uncommitted files sitting around
    # when running remote deployments. This may lead to inconsistent runs.
    try:
        repository_status = subprocess.check_output(
            ['hg', 'stat'], stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError):
        logger.error("Unable to check repository status. Is there an HG repository here?")
        sys.exit(1)
    else:
        if repository_status.strip():
            if args.dirty:
                logger.warning('Deploying dirty working copy due to --dirty.')
            else:
                logger.error(
                    'Can not deploy remotely with a dirty working copy:\n')
                logger.error(repository_status)
                sys.exit(1)

    config = ServiceConfig('.', [args.environment])
    config.scan()
    try:
        environment = config.service.environments[args.environment]
    except KeyError:
        known = ', '.join(sorted(config.existing_environments))
        logger.error('Environment "{}" unknown.\nKnown environments: {}'
                     .format(args.environment, known))
        sys.exit(1)

    environment.configure()

    deployment = RemoteDeployment(environment, args.ssh_user)
    deployment()
    notify('Deployment finished',
           '{} was deployed successfully.'.format(environment.name))


class RemoteDeployment(object):

    def __init__(self, environment, ssh_user):
        self.environment = environment
        self.ssh_user = ssh_user
        # It may be that the service definition isn't in the root of the
        # repository. As we expect `batou-remote` to be called with a working
        # directory that is the root, we simply make this relative to the
        # repository.
        self.service_base = os.getcwd()
        repository_base = self._repository_root().strip()
        self.service_base = self.service_base.replace(repository_base, '')

    def _repository_root(self):
        return subprocess.check_output(['hg', 'root'])

    def __call__(self):
        remotes = {}
        # XXX locking
        for host in self.environment.hosts.values():
            remote = RemoteHost(host, self)
            remotes[host] = remote

        # XXX optional
        pool = multiprocessing.pool.ThreadPool(20)
        pool.map(lambda x: x.connect(), remotes.values())
        #for x in remotes.values():
        #   x.connect()

        for component in self.environment.get_sorted_components():
            remote = remotes[component.host]
            remote.deploy_component(component)


class RemoteHost(object):

    def __init__(self, host, deployment):
        self.host = host
        self.deployment = deployment

    def connect(self):
        logger.info('{}: connecting'.format(self.host.fqdn))
        self.ssh = SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        self.ssh.set_missing_host_key_policy(AutoAddPolicy())
        self.ssh.connect(self.host.fqdn, username=self.deployment.ssh_user)
        self.sftp = self.ssh.open_sftp()
        self.cwd = []
        self.cwd.append(
            self.cmd('pwd', service_user=False, ensure_cwd=False).strip())
        self._bootstrap()

    def _bootstrap(self):
        """Ensure that the batou and project code base is current."""
        logger.info('{}: bootstrapping'.format(self.host.fqdn))
        bouncedir = self.cmd(u'echo -n ~/%s' % self.bouncedir_name(),
                             service_user=False)
        if not self.exists(bouncedir):
            self.cmd(u'hg init %s' % bouncedir, service_user=False)
        try:
            netloc = self.host.fqdn
            if self.deployment.ssh_user:
                netloc = '%s@%s' % (self.deployment.ssh_user, netloc)
            subprocess.check_output(['hg push --new-branch ssh://%s/%s' %
                                    (netloc, bouncedir)], shell=True)
        except subprocess.CalledProcessError, e:
            if e.returncode != 1:
                # Urks: 1 means: nothing to push
                raise
        service_user = self.deployment.environment.service_user
        self.remote_base = self.cmd('echo ~{}/deployment'.format(service_user))
        self.remote_base = self.remote_base.strip()
        if not self.exists(self.remote_base):
            self.cmd(u'hg clone %s %s' % (bouncedir, self.remote_base))
        else:
            with self.cd(self.remote_base):
                self.cmd(u'hg pull %s' % bouncedir)
        base = self.remote_base + self.deployment.service_base
        with self.cd(base):
            self.cmd(u'hg update -C %s' % self.deployment.environment.branch)
            if not self.exists('bin/python2.7'):
                self.cmd('virtualenv --no-site-packages --python python2.7 .')
            if not self.exists('bin/buildout'):
                # XXX We tend to have upgrade issues with setuptools. We used
                # to always bootstrap but it's becoming a pain.
                self.cmd('bin/python2.7 bootstrap.py -d')
            self.cmd('bin/buildout -t 15')

            self.batou = self.cmd('bin/batou-local --batch {} {}'
                    .format(self.deployment.environment.name,
                        self.host.fqdn), interactive=True)
            for root in self.host.components:
                root.component.remote_bootstrap(self)
            self._wait_for_remote_ready()
            self.remote_cmd('configure')

    def deploy_component(self, component):
        logger.info('Deploying {}/{}'.format(self.host.fqdn, component.name))
        self.remote_cmd('deploy {}'.format(component.name))

    def bouncedir_name(self):
        """Pick suitable name for hg repository bounce dir."""
        raw_name = u'bounce-%s-%s-%s' % (
            os.path.dirname(__file__).rsplit(u'/')[-1],
            self.deployment.environment.name,
            self.deployment.environment.branch)
        return re.sub(r'[^a-zA-Z0-9_.-]', u'_', raw_name)

    # Internal API

    def remote_cmd(self, cmd):
        logger.debug('Sending command to {}: {}'.format(self.host.name, cmd))
        self.batou[1].write(cmd + '\n')
        self.batou[1].flush()
        result = self._wait_for_remote_ready()
        if result != 'OK':
            raise RuntimeError(result)

    def set(self, component, attribute, value):
        self.remote_cmd('set {} {} {}'.format(component, attribute, value))

    def _wait_for_remote_ready(self):
        # Wait for the command to complete.
        logger.debug('starting to wait for remote {}'.format(self.host.name))
        lastline = 'OK'
        line = ''
        while True:
            char = self.batou[2].read(1)
            logger.debug('waiting for remote {} - got: {}'.format(self.host.name, repr(char)))
            if not char:
                raise RuntimeError('Empty response from server {}.'.format(self.host.name))
            line += char
            if line == '> ':
                logger.debug('done waiting for {}'.format(self.host.name))
                return lastline.strip()
            if char == '\n':
                line = line.strip()
                if line:
                    logger.info(line)
                    lastline = line
                    line = ''

    # Fabric convenience

    def cmd(self, cmd, service_user=True, ensure_cwd=True, interactive=False):
        """Execute `cmd` in the remote service user's context."""
        real_cmd = '{}'
        if service_user:
            real_cmd = 'sudo -u {0} -i bash -c "{{}}"'.format(
                self.deployment.environment.service_user)
        if ensure_cwd:
            real_cmd = real_cmd.format('cd {} && {{}}'.format(self.cwd[-1]))
        cmd = real_cmd.format(cmd)
        logger.debug(cmd)
        return self._cmd(cmd, interactive)

    def _cmd(self, cmd, interactive=False):
        chan = self.ssh._transport.open_session()
        #chan.get_pty()
        stdin = chan.makefile('wb', 0)
        stdout = chan.makefile('rb', 0)
        stderr = chan.makefile_stderr('rb', 0)
        chan.exec_command(cmd)
        if interactive:
            return chan, stdin, stdout, stderr
        status = chan.recv_exit_status()
        if status != 0:
            logger.error(stdout.read())
            logger.error(stderr.read())
            raise RuntimeError(status)
        result = stdout.read()
        logger.debug(result)
        logger.debug(stderr.read())
        return result

    def cd(self, path):
        return WorkingDirContextManager(self, path)

    def exists(self, path):
        path = self.ensure_working_dir(path)
        logger.debug('exists? ' + repr(path))
        try:
            self.sftp.stat(path)
        except Exception:
            return False
        return True

    def ensure_working_dir(self, path):
        if path[0] in ['/', '~']:
            return path
        return '{0}/{1}'.format(self.cwd[-1], path)


class WorkingDirContextManager(object):

    def __init__(self, remote, path):
        self.remote = remote
        self.path = path

    def __enter__(self):
        self.remote.cwd.append(self.path)

    def __exit__(self, exc_type, exc_value, traceback):
        self.remote.cwd.pop()
