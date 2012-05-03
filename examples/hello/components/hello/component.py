# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.component import Component
from batou.lib.file import File


class Hello(Component):

    mode = 0644

    def configure(self):
        self += File('hello', mode=self.mode, content='Hello world')
        self += File('foo/bar/baz', content='asdf', leading=True)


class RestrictedHello(Hello):

    mode = 0600
