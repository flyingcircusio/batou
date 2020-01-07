from batou.component import Component


class Component2(Component):

    def configure(self):
        self.require_one("sub")
        pass
