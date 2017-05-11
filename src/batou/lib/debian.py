from batou.component import Attribute, Component, platform
from batou.lib.cron import CronJob
import batou.lib.logrotate
import batou.lib.service
import batou.lib.supervisor


@platform('debian', batou.lib.service.Service)
class RebootCronjob(Component):

    def configure(self):
        self += CronJob(
            self.expand(
                '{{component.root.workdir}}/{{component.parent.executable}}'),
            timing='@reboot', logger=self.root.name)


# XXX can't use @platform since that's too late (see #12418)
class Supervisor(batou.lib.supervisor.Supervisor):

    pidfile = Attribute(str, 'var/supervisord.pid', map=True)


class Logrotate(batou.lib.logrotate.Logrotate):

    common_config = """\
daily
rotate 14
create
dateext
compress
notifempty
nomail
noolddir
missingok
sharedscripts
"""


@platform('debian', Logrotate)
class LogrotateCronjob(Component):

    def configure(self):
        self.directory = self.parent.workdir
        self += CronJob(
            self.expand(
                '/usr/sbin/logrotate -s {{component.directory}}/state'
                ' {{component.directory}}/logrotate.conf'),
            timing='45 2 * * *')
