from batou.component import Component
from batou.lib.buildout import Buildout
from batou.lib.service import Service


class Supervisor(Component):

    def configure(self):
        self.programs = self.require('programs', self.host)
        self += Buildout('supervisor', python='2.7')
        self += Service('bin/supervisord',
                        pidfile='var/supervisord.pid')

    def verify(self):
        self.assert_file_is_current(
            'var/supervisord.pid',
            ['.batou.buildout.success'] + [d['path'] for d in self.programs])

    def update(self):
        out, err = self.cmd('bin/supervisorctl pid')
        try:
            int(out)
        except ValueError:
            self.cmd('bin/supervisord')
        else:
            self.cmd('bin/supervisorctl reload')
