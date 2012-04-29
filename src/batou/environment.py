# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import os
import pwd


class Environment(object):
    """An environment is an allocation of components to hosts."""

    service_user = pwd.getpwuid(os.getuid()).pw_name
    host_domain = None
    branch = u'default'
    passphrase_file = None

    def __init__(self, name, service):
        self.name = name
        self.service = service
        self.hosts = {}

    def configure(self, config):
        """Pull options that come from cfg file out of `config` dict."""
        self.service_user = config.get('service_user', self.service_user)
        self.host_domain = config.get('host_domain', self.host_domain)
        self.branch = config.get('branch', self.branch)

    def normalize_host_name(self, hostname):
        """Ensure the given host name is an FQDN for this environment."""
        if not self.host_domain:
            return hostname
        domain = self.host_domain
        return '%s.%s' % (hostname.rstrip(domain), domain)

    def get_host(self, hostname):
        return self.hosts[self.normalize_host_name(hostname)]
