from batou import UpdateNeeded
from batou.component import Component
import os.path


class Hello(Component):

    asdf = None

    def verify(self):
        if not os.path.exists(self.root.name):
            raise UpdateNeeded()

    def update(self):
        with open(self.root.name, 'w') as f:
            f.write(self.root.name)


class Hello1(Hello):
    pass


class Hello2(Hello):
    pass


class Hello3(Hello):
    pass


class Hello4(Hello):
    pass


class Hello5(Hello):
    pass


class Hello6(Hello):
    pass
