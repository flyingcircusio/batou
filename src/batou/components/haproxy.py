# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.utils import Address, Hook
from batou.component import Component, step


class HAProxy(Component):
    """Load balancing component.

    Configuration attributes::
        [component:haproxy]
        haproxy_cfg = PATH
            path name of the configuration file
        restart = BOOL
            whether to call /etc/init.d/haproxy

    Expects hooks (given by backend_hooks) with the attributes:

    - server_name (string)
    - address (Address object)
    - backend (string)

    Provides hook 'haproxy:frontend' which has the following attributes:

    - address (Address object)

    """

    haproxy_cfg = '/etc/haproxy.cfg'
    restart = 'true'
    address = '${host.fqdn}:8002'
    backend_hooks = ()

    def setup_hooks(self):
        self.hooks['haproxy:frontend'] = Hook()

    def configure(self):
        self.config_attr('haproxy_cfg')
        self.config_attr('restart', 'bool')
        self.address = Address(self.config_attr('address'))
        self.hooks['haproxy:frontend'].address = self.address

        self.backends = {}
        for hook_name in self.backend_hooks:
            for hook in self.find_hooks(hook_name):
                servers = self.backends.setdefault(hook.backend, [])
                servers.append(hook)

    @step(1)
    def update_config(self):
        self.template('haproxy.cfg', target=self.haproxy_cfg)

    @step(2)
    def restart_haproxy(self):
        if not self.restart:
            self.log('skipping haproxy restart')
            return
        # restart instead of reload due to kernel bug
        self.cmd('sudo /etc/init.d/haproxy restart')
