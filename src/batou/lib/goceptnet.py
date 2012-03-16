"""gocept.net specific platform components.""" 
from batou.component import Component, platform
from batou.lib import file
import batou
import batou.lib.haproxy
import batou.lib.service
import batou.lib.ssh
import os.path


@platform('gocept.net', batou.lib.ssh.SSHDir)
class SSHDir(Component):
    """Sets the SSH dir to the one of the (current) service user
    and ensures a mode accepted by OpenSSH.
    """

    path = os.path.expanduser(u'~/.ssh')

    def configure(self):
        self.parent.path = self.path
        self += file.Directory(self.path)
        self += file.Mode(self.path, mode=0o711)


@platform('gocept.net', batou.lib.service.Service)
class UserInit(Component):
    """Register a service with user-init."""

    def configure(self):
        self.executable = self.parent.executable
        self.pidfile = self.parent.pidfile
        target = '/var/spool/init.d/{0}/{1}'.format(self.environment.service_user, self.service)
        init_source = os.path.join(
            os.path.dirname(__file__), 'resources', 'init.sh')
        self += file.Directory(os.path.dirname(target), leading=True)
        self += file.Content(target, source=init_source, is_template=True)
        self += file.Mode(target, mode=0o755)


@platform('gocept.net', batou.lib.haproxy.HAProxy)
class SystemWideHAProxy(Component):
    """gocep.net-specific component to integrate haproxy.
    """

    def configure(self):
        self += file.Symlink('/etc/haproxy.cfg', source='haproxy.cfg')

    def verify(self):
        self.assert_file_is_current('/var/run/haproxy.pid',
            ['/etc/haproxy.cfg'])

    def update(self):
        try:
            self.cmd('sudo /etc/init.d/haproxy reload')
        except:
            self.cmd('sudo /etc/init.d/haproxy restart')
