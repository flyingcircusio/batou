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
        self += buildout.Buildout(python='2.6')
        self += git.Clone('themes',
                source='git@github.com:deliverance/Deliverance.git')
        self += file.Content('rules.xml', is_template=True)

