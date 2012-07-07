# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.service import ServiceConfig
from ssh import AutoAddPolicy
from ssh.client import SSHClient
import argparse
import getpass
import logging
import os
import os.path
import re
import subprocess
import sys

logger = logging.getLogger('batou.remote')

def main():
    parser = argparse.ArgumentParser(
        description=u'Deploy a batou environment remotely.')
    parser.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x:x.replace('.cfg', ''))
    parser.add_argument(
        '--ssh-user', help='User to connect to via SSH', default=None)
    args = parser.parse_args()

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    for log in ['batou', 'ssh']:
        log = logging.getLogger(log)
        log.setLevel(logging.DEBUG)
        log.addHandler(handler)

    config = ServiceConfig('.', [args.environment])
    config.scan()
    environment = config.service.environments[args.environment]
    environment.configure()

    deployment = RemoteDeployment(environment, args.ssh_user)
    deployment()


class RemoteDeployment(object):

    def __init__(self, environment, ssh_user):
        self.environment = environment
        self.ssh_user = ssh_user
        # It may be that the service definition isn't in the root of the
        # repository. As we expect `batou-remote` to be called with a working
        # directory that is the root, we simply make this relative to the
        # repository.
        self.service_base = os.getcwd()
        repository_base = self._repository_config('bundle.mainreporoot')
        self.service_base = self.service_base.replace(repository_base, '')

    def _repository_config(self, key):
        config = subprocess.check_output('hg show', shell=True)
        for line in config.split('\n'):
            k, v = line.split('=', 1)
            if k == key:
                return v
        raise KeyError(key)

    def __call__(self):
        remotes = {}
        # XXX parallelization, locking
        for host in self.environment.hosts.values():
            remote = RemoteHost(host, self)
            remote.connect()
            remote.bootstrap()
            remotes[host] = remote

        for component in self.environment.ordered_components:
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
        self.cwd = [self.cmd('pwd', service_user=False, ensure_cwd=False).strip()]

    def bootstrap(self):
        """Ensure that the batou code base is current."""
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
        self.remote_base = self.cmd(
            'echo ~{}/deployment'.format(self.deployment.environment.service_user))
        self.remote_base = self.remote_base.strip()
        if not self.exists(self.remote_base):
            self.cmd(u'hg clone %s %s' % (bouncedir, self.remote_base))
        else:
            with self.cd(self.remote_base):
                self.cmd(u'hg pull %s' % bouncedir)
        # XXX self.setup_passphrase()
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
            self._wait_for_remote_ready()

    def _wait_for_remote_ready(self):
        # Wait for the command to complete.
        import pdb; pdb.set_trace() 
        lastline = None
        line = ''
        while True:
            char = self.batou[2].read(1)
            print char
            line += char
            if line == '> ':
                return lastline.strip()
            if char == '\n':
                logger.info(line)
                lastline = line
                line = line, ''

    def deploy_component(self, component):
        logger.info('Deploying {}/{}'.format(self.host.fqdn, component.name))
        self.batou[1].write(component.name + '\n')
        self.batou[1].flush()
        result = self._wait_for_remote_ready()
        if result != 'OK':
            raise RuntimeError(result)

    def bouncedir_name(self):
        """Pick suitable name for hg repository bounce dir."""
        raw_name = u'bounce-%s-%s-%s' % (
            os.path.dirname(__file__).rsplit(u'/')[-1],
            self.deployment.environment.name,
            self.deployment.environment.branch)
        return re.sub(r'[^a-zA-Z0-9_.-]', u'_', raw_name)

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
        stdin = chan.makefile('wb')
        stdout = chan.makefile('rb')
        stderr = chan.makefile_stderr('rb')
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
        logger.debug('exists? '+ repr(path))
        try:
            self.sftp.stat(path)
        except Exception, e:
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
