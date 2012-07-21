from batou import Component


class Zope(Component):

    def configure(self):
        self.require('zeo')
