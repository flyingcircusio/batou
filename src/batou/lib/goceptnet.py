"""Platform components specific to gocept.net."""
from batou.component import Component, platform
from batou.lib.file import File
import batou.lib.service
import os.path


@platform('gocept.net', batou.lib.service.Service)
class UserInit(Component):
    """Register a service with user-init."""

    def configure(self):
        self.executable = self.parent.executable
        self.pidfile = self.parent.pidfile
        if not os.path.isabs(self.pidfile):
            self.pidfile = os.path.join(self.root.workdir, self.pidfile)
        target = '/var/spool/init.d/{0}/{1}'.format(
            self.host.service_user,
            os.path.basename(self.parent.executable))
        init_source = os.path.join(
            os.path.dirname(__file__), 'resources', 'init.sh')
        self += File(
            target, source=init_source, mode=0o755, leading=True)
