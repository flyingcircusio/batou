from batou.component import Component
from batou.lib.file import File
from batou.utils import Address


class Hello(Component):

    password = "averysecretpassword"

    def configure(self):
        self.address = Address(f"my.{self.host.name}.{self.host.provisioner.target_host}", port=443)
        self += File('Hello', content='Hello World! {{component.address.listen}}')
