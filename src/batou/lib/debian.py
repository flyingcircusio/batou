from batou.component import Component, platform
from batou.lib.cron import CronJob
import batou.lib.service


@platform('debian', batou.lib.service.Service)
class RebootCronjob(Component):

    def configure(self):
        self += CronJob(
            self.expand(
                '{{component.root.workdir}}/{{component.parent.executable}}'),
            timing='@reboot', logger=self.root.name)
