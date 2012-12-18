import os
from batou.component import HookComponent, Component, platform
from batou.lib.file import File


class RotatedLogfile(HookComponent):

    namevar = 'path'
    key = 'batou.lib.logrotate:RotatedLogfile'

    args = ''
    prerotate = None
    postrotate = None

    def configure(self):
        super(RotatedLogfile, self).configure()
        self.path = os.path.join(self.workdir, self.path)
        self.path = self.map(self.path)
        self.args = map(str.strip, self.args.split(','))


class Logrotate(Component):

    logrotate_template = os.path.join(
        os.path.dirname(__file__), 'resources', 'logrotate.in')

    def configure(self):
        self.logfiles = self.require(RotatedLogfile.key, host=self.host)

        self.logrotate_conf = File('logrotate.conf',
            source=self.logrotate_template,
            is_template=True)
        self += self.logrotate_conf


@platform('gocept.net', Logrotate)
class GoceptNetRotatedLogrotate(Component):

    def configure(self):
        user = self.environment.service_user
        user_logrotate_conf = os.path.join('/var/spool/logrotate/', user)
        self += File(user_logrotate_conf,
                ensure='symlink',
                link_to=self.parent.logrotate_conf.path)
