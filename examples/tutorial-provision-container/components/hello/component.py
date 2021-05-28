from batou.component import Component
from batou.lib.file import File


class Hello(Component):

    password = "averysecretpassword"

    def configure(self):
        self += File('Hello', content='Hello World!')
