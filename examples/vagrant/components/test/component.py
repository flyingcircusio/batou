from batou.utils import Address
from batou.component import Component, Attribute
from batou.lib.file import File


class Test(Component):

    address = Attribute(Address, 'default:8080')

    def configure(self):
        self += File('test', content='asdf {{component.address.listen}}')
