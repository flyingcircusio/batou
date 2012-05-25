# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import collections
import itertools
import os
import pwd


class UnusedResource(Exception):
    """A provided resource was never used."""


def flatten(listOfLists):
    return itertools.chain.from_iterable(listOfLists)


class Environment(object):
    """An environment is an allocation of components to hosts."""

    service_user = pwd.getpwuid(os.getuid()).pw_name
    host_domain = None
    branch = u'default'
    platform = None

    def __init__(self, name, service):
        self.name = name
        self.service = service
        self.hosts = {}
        self.resources = {}

        # (Root) components that are interested in specific resources.
        self.subscribers = {}

    def from_config(self, config):
        """Pull options that come from cfg file out of `config` dict."""
        for key in ['service_user', 'host_domain', 'branch', 'platform']:
            if key in config:
                setattr(self, key, config[key])

    def configure(self):
        self.dirty = set()
        for host in self.hosts.values():
            self.dirty.update(host.components)

        while self.dirty:
            root = self.dirty.pop()
            self._reset_component_resources(root)
            root.component.sub_components = []
            # XXX If prepare fails we need to mark it dirty again and try a
            # different one. Probably needs a second dirty pool.
            root.component.prepare(self.service, self, host, root)

        unused_resources = set(self.resources) - set(self.subscribers)
        if unused_resources:
            raise UnusedResource(unused_resources)

    def normalize_host_name(self, hostname):
        """Ensure the given host name is an FQDN for this environment."""
        if not self.host_domain:
            return hostname
        domain = self.host_domain
        return '%s.%s' % (hostname.rstrip(domain), domain)

    def get_host(self, hostname):
        return self.hosts[self.normalize_host_name(hostname)]

    # Resource provider/user API

    def provide(self, component, key, value):
        values = self.resources.setdefault(key, collections.defaultdict(list))
        values[component.root].append(value)
        # Mark all subscribers for this key as dirty
        if key in self.subscribers:
            self.dirty.update(self.subscribers[key])

    def require(self, component, key):
        self.subscribers.setdefault(key, set()).add(component.root)
        return flatten(self.resources.get(key, {}).values())

    def _reset_component_resources(self, root):
        for key, resources in self.resources.items():
            if root in resources:
                del resources[root]
                self.dirty.update(self.subscribers[key])
