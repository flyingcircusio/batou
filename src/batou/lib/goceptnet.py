"""gocept.net specific platform components.""" 
import gocept.batou.lib


class Base(Component):

    platform = 'goceptnet'


class SSHDir(Component):
    """Sets the SSH dir to the one of the (current) service user
    and ensures a mode accepted by OpenSSH.
    """

    sshdir = os.path.expanduser(u'~/.ssh')
    _type = gocept.batou.lib.ssh.SSHDir

    def configure(self):
        self.parent.ssh_dir = self.ssh_dir
        self += file.Directory(self.sshdir)
        self += file.Mode(self.sshdir, mode=0o711)


class UserInit(Component):
    """Register a service with user-init."""

    namevar = 'service'

    def configure(self):
        target = '/var/spool/init.d/{0}/{1}'.format(self.environment.service_user, self.service)
        init_source = os.path.join(
            os.path.dirname(__file__), 'resources', 'init.sh')
        self += file.Directory(os.path.dirname(target), leading=True)
        self += file.Content(target, source=init_source, is_template=True)
        self += file.Mode(target, mode=0o755)


class Supervisor(Component):
    """Registers the installed supervisor with userinit."""

    _type = gocept.batou.lib.supervisor.Supervisor

    def configure(self):
        self += UserInit('supervisor', executable='bin/supervisord')


for component in globals():
    if hasattr(component, '_type'):
        _type.platforms.add(component)
