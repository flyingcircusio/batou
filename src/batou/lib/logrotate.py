from batou.component import HookComponent, Component, platform
from batou.lib.file import File
import os.path
import pkg_resources


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
        self.args = list(map(str.strip, self.args.split(',')))


class Logrotate(Component):

    common_config = b''
    logrotate_template = pkg_resources.resource_string(
        __name__, 'resources/logrotate.in')

    def configure(self):
        self.logfiles = self.require(RotatedLogfile.key, host=self.host)
        self.logfiles.sort(key=lambda logfile: logfile.path)

        config = self.common_config + self.logrotate_template
        self.logrotate_conf = File('logrotate.conf', content=config)
        self += self.logrotate_conf


@platform('gocept.net', Logrotate)
class GoceptNetRotatedLogrotate(Component):

    def configure(self):
        user = self.host.service_user
        user_logrotate_conf = os.path.join('/var/spool/logrotate/', user)
        self += File(
            user_logrotate_conf,
            ensure='symlink',
            link_to=self.parent.logrotate_conf.path)
