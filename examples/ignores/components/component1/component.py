from batou.component import Component


class Component1(Component):

    def configure(self):
        self.provide("asdf", "test")
