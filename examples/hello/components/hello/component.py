# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.component import Component
from batou.lib import file


class Hello(Component):

    mode = 0644

    def configure(self):
        self += file.Mode('hello', mode=self.mode)
        self += file.Content('hello', content='Hello world')


class RestrictedHello(Hello):

    mode = 0600
