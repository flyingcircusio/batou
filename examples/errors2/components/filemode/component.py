from batou.component import Component
from batou.lib.file import File


class FileMode(Component):

    def configure(self):
        self += File('new-file.txt', mode='wrongmode')
