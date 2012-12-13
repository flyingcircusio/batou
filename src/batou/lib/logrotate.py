import os
import inspect
from batou.component import HookComponent
from batou.component import Component
from batou.lib.file import File


class RotatedLogfile(HookComponent):

    namevar = 'path'
    key = 'osha.lib.logrotate:RotatedLogfile'

    args = ''

    def configure(self):
        super(RotatedLogfile, self).configure()
        self.path = os.path.join(self.workdir, self.path)
        self.path = self.map(path)
        self.args = map(str.strip, self.args.split(','))


class Logrotate(Component):

    logrotate_template = os.path.join(
        os.path.dirname(__file__), 'resources', 'logrotate.in')

    def configure(self):
        self.logfiles = self.require(RotatedLogfile.key, host=self.host)

        self += File('logrotate.conf',
            source=self.logrotate_template,
            is_template=True)
