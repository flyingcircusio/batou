# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.component import Component
from batou.lib import file, buildout, git, python
from batou.utils import Address


class Deliverance(Component):
    # Later: Hooks: http server, supervisor, upstream http

    address = Address('localhost:8080')
    upstream = Address('localhost:7001')
    dev_user = 'admin'
    dev_password = 'password'

    def configure(self):
        venv = python.VirtualEnv('2.6')
        self += venv
        self += buildout.Buildout(python=venv.python)
        self += git.Clone('themes',
                source='git@github.com:deliverance/Deliverance.git')
        self += file.Content('rules.xml', is_template=True)


class Hello(Component):

    mode = 0644

    def configure(self):
        self += file.Mode('hello', mode=self.mode)
        self += file.Content('hello', content='Hello world')


class RestrictedHello(Hello):

    mode = 0600
