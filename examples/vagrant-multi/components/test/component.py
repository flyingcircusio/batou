import batou.component
import batou.lib.file


class Test(batou.component.Component):

    def configure(self):
        self += batou.lib.file.File('base-component')


@batou.component.platform('nixos', Test)
class TestNixos(batou.component.Component):

    def configure(self):
        self += batou.lib.file.File('i-am-nixos')


@batou.component.platform('ubuntu', Test)
class TestUbuntu(batou.component.Component):

    def configure(self):
        self += batou.lib.file.File('i-am-ubuntu')
