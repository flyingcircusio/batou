from batou.component import Component
from batou.lib.file import File


class ZEO(Component):

    def configure(self):
        self.provide('zeo', '127.0.0.1:9000')
        # As reported in #11183 we had a regression that caused the
        # sub-component to remove the provided values accidentally.
        self += File('asdf', content='asdf')
