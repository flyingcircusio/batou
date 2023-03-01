from time import sleep

from batou.component import Component
from batou.lib.file import File


class Takeslongtime(Component):
    def verify(self):
        sleep(2)
