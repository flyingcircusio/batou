import batou.component
import batou.lib.cron
import os.path


class Service(batou.component.Component):
    """A generic component to provide a system service.

    Platform-specific components need to perform the work necessary
    to ensure startup and shutdown of the executable correctly.
    """

    namevar = 'executable'

    pidfile = None  # The pidfile as written by the services' executable.


@batou.component.platform('vagrant', Service)
class UserInit(batou.component.Component):
    """Register a service with user-init."""

    def configure(self):
        executable = os.path.join(
            self.parent.workdir, self.parent.executable)
        self += batou.lib.cron.CronJob(
            executable,
            timing='@reboot')
