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
        self.remote_base = '~%s/deployment' % self.environment.service_user

    def _connect(self):
        self.ssh = SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
        self.ssh.set_missing_host_key_policy(AutoAddPolicy())
        self.ssh.connect(self.host.fqdn)
        self.sftp = self.ssh.open_sftp()
        self.cwd = []
        self.cwd = [self.cmd('pwd', service_user=False).strip()]

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
        return
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

    def cmd(self, cmd, service_user=True):
        """Execute `cmd` in the remote service user's context."""
        prefixes = []
        if service_user:
            prefixes.append('sudo -S')
        prefixes.append('cd %s &&' % '/'.join(self.cwd))
        prefixes.append(cmd)
        cmd = ' '.join(prefixes)
        logger.debug(cmd)
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        result = stdout.read()
        logger.debug(result)
        logger.debug(stderr.read())
        return result

    def cd(self, path):
        return WorkingDirContextManager(self, path)

    def exists(self, path):
        path = '/'.join(self.cwd+[path])
        logger.debug('exists? '+path)
        try:
            self.sftp.stat(path)
        except:
            return False
        return True


class WorkingDirContextManager(object):

    def __init__(self, remote, path):
        self.remote = remote
        self.path = path

    def __enter__(self):
        self.remote.cwd.append(self.path)

    def __exit__(self, exc_type, exc_value, traceback):
        self.remote.pop()
