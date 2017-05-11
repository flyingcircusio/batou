from batou import UpdateNeeded
from batou.component import Component
import os.path


class Hello(Component):

    asdf = None

    prov = None
    req = None

    def verify(self):
        self.log('%s verify: asdf=%s', self, self.asdf)
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


class HelloReq(Component):

    def configure(self):
        self.require('i-need')
        self.log('Pre sub')
        self += Sub()
        self.log('Post sub')


class HelloProv(Component):

    def configure(self):
        self.provide('i-need', self)
        self.log('Provide')


class Sub(Component):

    def configure(self):
        self.log('Sub!')
