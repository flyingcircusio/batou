from batou.component import Component


class ComponentSub(Component):

    def configure(self):
        self.provide('sub', 'test')
