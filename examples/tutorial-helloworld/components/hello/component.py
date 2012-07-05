from batou.component import Component
from batou.lib.file import File

class Hello(Component):

    def configure(self):
        self += File('hello', content='Hello world')
