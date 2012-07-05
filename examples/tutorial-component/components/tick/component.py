from batou.component import Component
from batou.lib.file import File


class Tick(Component):

    def configure(self):
        self += File('hello', source='tick.sh', mode=0755)
        self.provide('programs',
                     self.expand('10 tick {{component.workdir}}/tick.sh true'))
