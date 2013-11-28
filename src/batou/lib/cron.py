from batou import UpdateNeeded
from batou.component import Component, HookComponent, platform
from batou.lib.file import File
import pkg_resources


class CronJob(HookComponent):

    namevar = 'command'
    key = 'batou.lib.cron:CronJob'

    args = ''
    timing = None
    logger = None
    user = None

    def format(self):
        if self.timing is None:
            raise ValueError('Required timing value missing from cron job %r.'
                             % self.command)
        self.user = ' %s' % self.user if self.user else ''
        line = self.expand(
            '{{component.timing}}{{component.user}}'
            ' {{component.command}} {{component.args}}')
        if self.logger:
            line += self.expand(' 2>&1 | logger -t {{component.logger}}')
        return line


def ignore_comments(data):
    lines = data.splitlines()
    lines = filter(lambda x: not x.startswith('#'), lines)
    return '\n'.join(lines)


class CronTab(Component):

    crontab_template = pkg_resources.resource_filename(
        __name__, 'resources/crontab')
    mailto = None
    filename = 'crontab'
    key = CronJob.key
    user = None

    def configure(self):
        self.jobs = self.require(self.key, host=self.host)
        self.jobs.sort(key=lambda job: job.command + ' ' + job.args)
        for job in self.jobs:
            job.user = self.user
        self.crontab = File(
            self.filename, source=self.crontab_template)
        self += self.crontab


class InstallCrontab(Component):

    def configure(self):
        self.crontab = self.parent.crontab

    def verify(self):
        try:
            current, _ = self.cmd('crontab -l', silent=True)
        except:
            current = ''
        current = ignore_comments(current)
        new = ignore_comments(self.crontab.content)
        if new != current:
            raise UpdateNeeded()

    def update(self):
        self.cmd(self.expand('crontab {{component.crontab.path}}'))


@platform('gocept.net', CronTab)
class FCInstallCrontab(InstallCrontab):
    pass


@platform('debian', CronTab)
class DebianInstallCrontab(InstallCrontab):
    pass
