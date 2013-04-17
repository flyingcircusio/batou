from batou import UpdateNeeded
from batou.component import Component, HookComponent, platform
from batou.lib.file import File
import os


class CronJob(HookComponent):

    namevar = 'command'
    key = 'batou.lib.cron:CronJob'

    args = ''
    timing = None
    logger = None

    def format(self):
        line = self.expand('{{component.timing}} {{component.command}} {{component.args}}')
        if self.logger:
            line += self.expand(' 2>&1 | logger -t {{component.logger}}')
        return line


def ignore_comments(data):
    lines = data.splitlines()
    lines = filter(lambda x:not x.startswith('#'),
                   lines)
    return '\n'.join(lines)


class CronTab(Component):

    crontab_template = os.path.join(
        os.path.dirname(__file__), 'resources', 'crontab')

    def configure(self):
        self.jobs = self.require(CronJob.key, host=self.host)
        self.jobs.sort(key=lambda job:job.command + ' ' + job.args)
        self.crontab = File('crontab',
            source=self.crontab_template,
            is_template=True)
        self += self.crontab


@platform('gocept.net', CronTab)
class GoceptNetCrontab(Component):

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
