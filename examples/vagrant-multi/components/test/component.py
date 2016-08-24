from batou.utils import Address
from batou.component import Component, Attribute, platform
from batou.lib.file import File
from batou.lib.buildout import Buildout


class Test(Component):

    address = Attribute(Address, 'default:8080')

    def configure(self):
        self += File('test', content='asdf {{component.address.listen}}')
        self += Buildout(version='2.3.1',
                         python='2.7',
                         setuptools='17.1')


@platform('nixos')
class TestNixos(Component):

    def configure(self):
        self += File('i-am-nixos')


@platform('ubuntu')
class TestUbuntu(Component):

    def configure(self):
        self += File('i-am-ubuntu')
