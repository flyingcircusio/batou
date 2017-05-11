from batou.component import Component
from batou.lib.file import File


class Tick(Component):

    def configure(self):
        tick = File('tick.sh',
                    source='tick.sh',
                    mode=0755)
        self += tick
        self.provide('programs',
                     dict(name='tick',
                          path=tick.path,
                          priority=10))
