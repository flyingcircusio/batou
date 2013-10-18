from batou.component import Component
from batou.lib.file import File


class Example(Component):

    def configure(self):
        self += File('hello', content='Hello world!')
