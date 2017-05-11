from batou.component import Component


class Cycle1(Component):

    def configure(self):
        self.require('a')
        self.provide('b', 1)


class Cycle2(Component):

    def configure(self):
        self.require('b')
        self.provide('a', 1)
