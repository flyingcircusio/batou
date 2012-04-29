# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.passphrase import PassphraseFile
import atexit
import fabric.api
import fabric.contrib.files
import fabric.main
import os
import re
import subprocess


def main():
    # Bootstrap this batou project on the remote hosts and invoke local channel
    # deployments there.
    # This fabric call will turn around, use our stub fabfile which will then
    # in turn use the FabricTask wrapper to bootstrap remote hosts and
    # invoke us over there.
    fabric.main.main()


class FabricTask(fabric.tasks.Task):
    """Adapter to bind fabric's task API and our environment/hosts together."""

    def __init__(self, config, name):
        self.config = config
        self.service = config.service
        self.environment = config.service.environments[name]
        self.name = name

    @classmethod
    def from_config(cls, config):
        tasks = {}
        for name in config.service.environments:
            tasks[name] = task = cls(config, name)
            task.__doc__ = 'Deploy to %s environment' % name
        return tasks

    def get_hosts(self, arg_hosts, arg_roles, arg_exclude_hosts, env=None):
        """Compute effective subset if hosts have been named on commandline."""
        allowed_hosts = set(self.environment.hosts)
        if arg_hosts:
            arg_hosts = set((self.environment.normalize_host_name(h)
                             for h in arg_hosts))
            return set(arg_hosts).intersection(allowed_hosts)
        return allowed_hosts

    def setup_passphrase(self):
        """Set up passphrase locally."""
        self._pf = PassphraseFile(u'environment "%s"' % self.environment.name)
        self.passphrase_file = self._pf.__enter__()
        atexit.register(self._pf.__exit__)

    def transfer_passphrase(self):
        """Set up passphrase on remote host in .batou-passphrase"""
        fabric.api.put(self.passphrase_file, u'/tmp/batou-passphrase')
        self.cmd(u'install -m0600 /tmp/batou-passphrase %s/.batou-passphrase' %
                 self.remote_base)
        fabric.api.run(u'rm -f /tmp/batou-passphrase')

    def bouncedir_name(self):
        """Pick suitable name for hg repository bounce dir."""
        raw_name = u'bounce-%s-%s-%s' % (
            os.path.dirname(__file__).rsplit(u'/')[-1], self.environment.name,
            self.environment.branch)
        return re.sub(r'[^a-zA-Z0-9_.-]', u'_', raw_name)

    def bootstrap(self):
        """Ensure that the batou code base is current."""
        bouncedir = fabric.api.run(u'echo -n ~/%s' % self.bouncedir_name())
        if not self.exists(bouncedir):
            fabric.api.run(u'hg init %s' % bouncedir)
        try:
            subprocess.check_call(['hg push -f ssh://%s/%s' %
                                   (fabric.api.env.host, bouncedir)],
                                  shell=True)
        except subprocess.CalledProcessError, e:
            if e.returncode != 1:
                # 1 means: nothing to push
                raise
        if not self.exists(self.remote_base):
            self.cmd(u'hg clone %s %s' % (bouncedir, self.remote_base))
        else:
            with self.cd(self.remote_base):
                self.cmd(u'hg pull %s' % bouncedir)
        self.transfer_passphrase()
        with self.cd(self.remote_base):
            self.cmd(u'hg update -C %s' % self.environment.branch)
            if not self.exists('bin/python2.7'):
                self.cmd('virtualenv --no-site-packages --python python2.7 .')
            # XXX We're having upgrade issues with setuptools. We always
            # bootstrap, for now.
            self.cmd('bin/python2.7 bootstrap.py')
            self.cmd('bin/buildout -t 15')

    def run(self):
        """This is fabric's `run`. We would call this 'deploy'."""
        self.setup_passphrase()
        # Lazy loading of the config to limit this to the environment we
        # actually need.
        self.environment = self.config.service.environments[self.name]
        self.environment.passphrase_file = self.passphrase_file
        self.name = self.environment.name
        self.remote_base = '~%s/deployment' % self.environment.service_user
        self.config.configure_components(self.environment)

        host = self.environment.hosts[fabric.api.env.host]
        self.bootstrap()
        with fabric.api.cd(self.remote_base):
            # Run local batou deployment on remote host
            self.cmd('bin/batou-local %s %s' %
                     (self.environment.name, host.fqdn))

    # Fabric convenience

    def cmd(self, cmd):
        """Execute `cmd` in the remote service user's context."""
        return fabric.api.sudo(cmd, user=self.environment.service_user)

    def cd(self, path):
        return fabric.api.cd(path)

    def exists(self, path):
        return fabric.contrib.files.exists(path)
