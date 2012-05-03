# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.component import Component
from batou.lib.file import File
from batou.lib.buildout import Buildout
from batou.lib.git import Clone
from batou.utils import Address


class Deliverance(Component):
    # Later: Hooks: http server, supervisor, upstream http

    address = '${host.fqdn}:8080'
    upstream = '${host.fqdn}:7001'      # XXX lookup via hook
    dev_user = 'admin'
    dev_password = 'password'

    def configure(self):
        self.hooks['deliverance:http'] = self.address = Address(self.expand(self.address))
        self.upstream = Address(self.expand(self.upstream))
        self.hooks['supervisor'] = (
            '30 deliverance (startsecs=10) {0}/bin/deliverance-proxy '
            '[{0}/rules.xml] true'.format(self.root.workdir))

        self += Buildout(python='2.6')
        self += Clone('themes',
                source='git@github.com:deliverance/Deliverance.git')
        self += File('rules.xml', is_template=True)
