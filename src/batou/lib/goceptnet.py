"""gocept.net specific platform components."""
from batou.component import Component, platform
from batou.lib.file import File
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
        self += File(self.path, ensure='directory', mode=0o711)


@platform('gocept.net', batou.lib.service.Service)
class UserInit(Component):
    """Register a service with user-init."""

    def configure(self):
        self.executable = self.parent.executable
        self.pidfile = self.parent.pidfile
        target = '/var/spool/init.d/{0}/{1}'.format(
            self.environment.service_user,
            os.path.basename(self.parent.executeable))
        init_source = os.path.join(
            os.path.dirname(__file__), 'resources', 'init.sh')
        self += File(target,
                source=init_source,
                is_template=True,
                mode=0o755,
                leading=True)


@platform('gocept.net', batou.lib.haproxy.HAProxy)
class SystemWideHAProxy(Component):
    """gocep.net-specific component to integrate haproxy.
    """

    def configure(self):
        self += file.File('/etc/haproxy.cfg', source='haproxy.cfg')

    def verify(self):
        self.assert_file_is_current('/var/run/haproxy.pid',
            ['/etc/haproxy.cfg'])

    def update(self):
        try:
            self.cmd('sudo /etc/init.d/haproxy reload')
        except:
            self.cmd('sudo /etc/init.d/haproxy restart')
