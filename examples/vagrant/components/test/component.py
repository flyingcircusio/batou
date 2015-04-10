from batou.component import Component
from batou.lib.file import File


class Test(Component):

    def configure(self):
        self += File('test', content='asdf')
