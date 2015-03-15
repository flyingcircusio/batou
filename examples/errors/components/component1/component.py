from batou.component import Component, Attribute


class Component1(Component):

    do_what_is_needed = Attribute('literal', None)


class Component2(Component):

    this_does_exist = Attribute('literal', None)


class Component3(Component):

    def configure(self):
        self.provide('frontend', 'test00.gocept.net')
        self.provide('backend', '192.168.0.1')


class Component4(Component):

    def configure(self):
        self.require('application')
