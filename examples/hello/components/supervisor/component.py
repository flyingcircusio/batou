# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.utils import Address
from batou.component import Component
from batou.lib import file
from batou.lib.service import Service
from batou.lib.buildout import Buildout
from batou import UpdateNeeded
import os


class Supervisor(Component):

    http_port = Address('localhost:9001')

    def configure(self):
        self.programs = self.find_hooks('supervisor', self.host)
        self += Buildout(
                    python='2.7',
                    config=file.Content('buildout.cfg', is_template=True))
        service = Service('bin/supervisord', pidfile='var/supervisor.pid')
        self += service

    def verify(self):
        self.assert_file_is_current('var/supervisord.pid',
                ['.batou.buildout.success'])
        try:
            self.cmd('bin/supervisorctl pid')
        except Exception:
            raise UpdateNeeded()

    def update(self):
        try:
            self.cmd('bin/supervisorctl reload')
        except:
            self.cmd('bin/supervisord')
