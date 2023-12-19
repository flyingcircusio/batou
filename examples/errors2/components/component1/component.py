from batou.component import Attribute, Component


class Component1(Component):

    do_what_is_needed = Attribute("literal", default=None)
    my_attribute = None


class Component2(Component):

    this_does_exist = Attribute("literal", default=None)


class Component3(Component):
    def configure(self):
        self.provide("frontend", "test00.gocept.net")
        self.provide("backend", "192.168.0.1")
        self += SubComponent("sub sub")


class Component4(Component):
    def configure(self):
        self.require("application")


class Component5(Component):
    attribute_cannot_be_expanded = Attribute("literal", default=None)

    def configure(self):
        print(self.attribute_cannot_be_expanded)


class SubComponent(Component):

    namevar = "aname"

    def configure(self):
        self.provide("sub", self)
