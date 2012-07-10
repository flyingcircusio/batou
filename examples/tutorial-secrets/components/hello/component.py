from batou.component import Component
from batou.lib.file import File


class Hello(Component):

    def configure(self):
        secrets = self.require('secrets')[0]
        magic_word = secrets.get('hello', 'magicword')
        self += File('hello',
            content='The magic word is {}'.format(magic_word))
