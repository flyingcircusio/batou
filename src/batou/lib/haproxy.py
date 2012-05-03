# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.utils import Address, Hook
from batou.component import Component
from batou.lib.file import File


class HAProxy(Component):
    """Load balancing component.

    Expects hooks (given by backend_hooks) with the attributes:

    - server_name (string)
    - address (Address object)
    - backend (string)

    Provides hook 'haproxy:frontend' which is an Address object.

    """

    address = '${host.fqdn}:8002'
    backend_hook = None

    def configure(self):
        self.hooks['frontend'] = self.address = Address(self.expand(self.address))
        self.servers = self.find_hooks(self.backend_hook)
        self += File('haproxy.cfg', is_template=True)
