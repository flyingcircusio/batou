# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.passphrase import PassphraseFile
from batou.service import ServiceConfig
from ssh.client import SSHClient
from ssh import AutoAddPolicy
import argparse
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
    args = parser.parse_args()

    batou = logging.getLogger('batou')
    batou.setLevel(-1000)
    handler = logging.StreamHandler()
    handler.setLevel(-1000)
    batou.addHandler(handler)

    config = ServiceConfig('.', [args.environment])
    config.scan()
    environment = config.service.environments[args.environment]

    for host in environment.hosts.values():
        deployment = RemoteDeployment(host, environment)
        deployment()


class RemoteDeployment(object):

    def __init__(self, host, environment):
        self.host = host
        self.environment = environment

    def _connect(self):
        logger.debug('Connecting to {}'.format(self.host.fqdn))
        self.ssh = SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        self.ssh.set_missing_host_key_policy(AutoAddPolicy())
        self.ssh.connect(self.host.fqdn)
        self.sftp = self.ssh.open_sftp()
        self.cwd = [self.cmd('pwd', service_user=False, ensure_cwd=False).strip()]

    def __call__(self):
        self._connect()
        self.bootstrap()
        with self.cd(self.remote_base):
            self.cmd('bin/batou-local %s %s' %
                     (self.environment.name, self.host.fqdn))

    def bouncedir_name(self):
        """Pick suitable name for hg repository bounce dir."""
        raw_name = u'bounce-%s-%s-%s' % (
            os.path.dirname(__file__).rsplit(u'/')[-1], self.environment.name,
            self.environment.branch)
        return re.sub(r'[^a-zA-Z0-9_.-]', u'_', raw_name)

    def bootstrap(self):
        """Ensure that the batou code base is current."""
        bouncedir = self.cmd(u'echo -n ~/%s' % self.bouncedir_name(),
                             service_user=False)
        if not self.exists(bouncedir):
            self.cmd(u'hg init %s' % bouncedir, service_user=False)
        try:
            subprocess.check_call(['hg push --new-branch ssh://%s/%s' %
                                   (self.host.fqdn, bouncedir)], shell=True)
        except subprocess.CalledProcessError, e:
            if e.returncode != 1:
                # 1 means: nothing to push
                raise
        self.remote_base = self.cmd(
            'echo ~{}/deployment'.format(self.environment.service_user))
        self.remote_base = self.remote_base.strip()
        if not self.exists(self.remote_base):
            self.cmd(u'hg clone %s %s' % (bouncedir, self.remote_base))
        else:
            with self.cd(self.remote_base):
                self.cmd(u'hg pull %s' % bouncedir)
        # XXX self.setup_passphrase()
        with self.cd(self.remote_base):
            self.cmd(u'hg update -C %s' % self.environment.branch)
            if not self.exists('bin/python2.7'):
                self.cmd('virtualenv --no-site-packages --python python2.7 .')
            # XXX We're having upgrade issues with setuptools. We always
            # bootstrap, for now.
            self.cmd('bin/python2.7 bootstrap.py')
            self.cmd('bin/buildout -t 15')

    # Fabric convenience

    def cmd(self, cmd, service_user=True, ensure_cwd=True):
        """Execute `cmd` in the remote service user's context."""
        real_cmd = '{}'
        if service_user:
            real_cmd = 'sudo -u {0} -i bash -c "{{}}"'.format(
                self.environment.service_user)
        if ensure_cwd:
            real_cmd = real_cmd.format('cd {} && {{}}'.format(self.cwd[-1]))
        cmd = real_cmd.format(cmd)
        logger.debug(cmd)
        return self._cmd(cmd)

    def _cmd(self, cmd):
        chan = self.ssh._transport.open_session()
        chan.exec_command(cmd)
        stdin = chan.makefile('wb')
        stdout = chan.makefile('rb')
        stderr = chan.makefile_stderr('rb')
        status = chan.recv_exit_status()
        if status != 0:
            raise RuntimeError(status, stderr.read())
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
