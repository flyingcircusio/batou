from batou.component import Component
from batou.lib.buildout import Buildout


class Supervisor(Component):

    def configure(self):
        self.programs = self.require('programs')
        self += Buildout('supervisor', python='2.7')

    def verify(self):
        self.assert_file_is_current(
            'var/supervisord.pid', ['.batou.buildout.success'])

    def update(self):
        out, err = self.cmd('bin/supervisorctl pid')
        try:
            int(out)
        except TypeError:
            self.cmd('bin/supervisord')
        else:
            self.cmd('bin/supervisorctl reload')
