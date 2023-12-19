from batou.component import Attribute, Component
from batou.lib.file import File


class World(Component):
    def configure(self):
        self += File("hello.txt", content="Hello World")
        # raise Exception("Programmers make errors too :)")


class Hello(Component):
    public_name = Attribute()

    def configure(self):
        self += World()
