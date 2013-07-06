from batou.component import Component
from batou.lib.file import File


class Hello(Component):

    magic_word = None

    def configure(self):
        self += File('hello',
            content='The magic word is {}.\n'.format(self.magic_word))
