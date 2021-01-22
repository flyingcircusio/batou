from batou.utils import Address
from batou.component import Component, Attribute
from batou.lib.file import File
from batou.lib.buildout import Buildout


class Test(Component):

    address = Attribute(Address, "default:8080")

    def configure(self):
        self += File("test", content="asdf {{component.address.listen}}")
        self += Buildout(version="2.3.1", python="2.7", setuptools="17.1")
