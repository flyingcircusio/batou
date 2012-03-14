# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.utils import Address
from batou.component import Component
from batou.lib import file, buildout
from batou import UpdateNeeded
import os



class UserInit(Component):

    namevar = 'service'

    def configure(self):
        target = '/var/spool/init.d/{0}/{1}'.format(self.environment.service_user, self.service)
        self += file.Directory(os.path.dirname(target), leading=True)
        self += file.Content(target, source=self.source, is_template=True)
        self += file.Mode(target, mode=0o755)


class Supervisor(Component):

    http_port = Address('localhost:9001')

    def configure(self):
        self.programs = self.find_hooks('.*:supervisor', self.host)
        self += buildout.Buildout(
                    python='2.7',
                    config=file.Content('buildout.cfg', is_template=True))
        # self += UserInit('supervisor', source='init.sh')

    def verify(self):
        self.assert_file_is_current('var/supervisord.pid',
                ['.batou.buildout.success'])

    def update(self):
        try:
            self.cmd('bin/supervisorctl reload')
        except:
            self.cmd('bin/supervisord')
