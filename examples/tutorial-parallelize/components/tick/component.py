import time

from batou import UpdateNeeded
from batou.component import Component
from batou.lib.file import File


class Tick(Component):
    def configure(self):
        tick = File("tick.sh", source="tick.sh", mode=0o755)
        self += tick
        self.provide("programs", dict(name="tick", path=tick.path, priority=10))

    def verify(self):
        raise UpdateNeeded()

    def update(self):
        time.sleep(5)


class Tick2(Tick):
    pass


class Tick3(Tick):
    pass


class Tick4(Tick):
    pass


class Tick5(Tick):
    pass
