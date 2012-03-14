# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.utils import Address, Hook
from batou.component import Component
from batou.lib import file


class GoceptNet(Component):
    """GoceptNet-specific component to integrate haproxy.
    """

    def configure(self):
        self += file.Symlink('/etc/haproxy.cfg', source='haproxy.cfg')

    def verify(self):
        self.assert_file_is_current('/var/run/haproxy.pid',
            ['/etc/haproxy.cfg'])

    def update(self):
        try:
            self.cmd('sudo /etc/init.d/haproxy reload')
        except:
            self.cmd('sudo /etc/init.d/haproxy restart')


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
    platforms = [GoceptNet]

    def configure(self):
        self.hooks['frontend'] = self.address = Address(self.expand(self.address))
        self.servers = self.find_hooks(self.backend_hook)
        self += file.Content('haproxy.cfg', is_template=True)
