from batou.component import Component, Attribute


class Component1(Component):

    do_what_is_needed = Attribute("literal", None)


class Component2(Component):

    this_does_exist = Attribute("literal", None)


class Component3(Component):
    def configure(self):
        self.provide("frontend", "test00.gocept.net")
        self.provide("backend", "192.168.0.1")
        self += SubComponent("sub sub")


class Component4(Component):
    def configure(self):
        self.require("application")


class SubComponent(Component):

    namevar = "aname"

    def configure(self):
        self.provide("sub", self)
