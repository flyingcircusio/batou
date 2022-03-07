from batou.component import Component


class Fail(Component):
    def configure(self):
        self.require("asdf")
        self.provide("fail", None)

    def verify(self):
        raise RuntimeError("Fail!")


class Fail2(Component):
    def configure(self):
        self.require("fail")

    def verify(self):
        raise RuntimeError("Fail!")
