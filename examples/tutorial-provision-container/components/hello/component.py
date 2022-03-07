from batou.component import Component
from batou.lib.file import File
from batou.utils import Address


class Hello(Component):

    password = "averysecretpassword"

    def configure(self):
        self.address = Address(self.host.aliases.my, port=443)
        self += File(
            "Hello",
            content=(
                "Hello World! {{host.aliases.my}} "
                "= {{component.address.listen}} "
            ),
        )
