# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.utils import Address
from batou.component import Component
from batou.lib import file, buildout
from batou import UpdateNeeded
import os


class Supervisor(Component):

    http_port = Address('localhost:9001')

    def configure(self):
        self.programs = self.find_hooks('supervisor', self.host)
        self += buildout.Buildout(
                    python='2.7',
                    config=file.Content('buildout.cfg', is_template=True))

    def verify(self):
        self.assert_file_is_current('var/supervisord.pid',
                ['.batou.buildout.success'])

    def update(self):
        try:
            self.cmd('bin/supervisorctl reload')
        except:
            self.cmd('bin/supervisord')
