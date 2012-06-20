# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import collections
import logging
import os
import pwd
from batou.utils import flatten
from batou import NonConvergingWorkingSet, UnusedResource


logger = logging.getLogger(__name__)


class Resources(object):
    """A registry for resources.

    Resources are mappings of keys to lists of values.

    Components can `provide` resources by specifying a key and a value.

    Components can retrieve all resources for a key by `requiring` the key.
    Optionally components can limit the values returned to a specific host.

    The registry keeps track of which component depends on what 
    resources.
    """

    def __init__(self):
        self.resources = {}
        self.subscribers = {}
        self.pending_dependencies = set()

    def provide(self, component, key, value):
        values = self.resources.setdefault(key, collections.defaultdict(list))
        values[component.root].append(value)
        self.pending_dependencies.update(self.subscribers.get(key, ()))

    def require(self, component, key, host=None):
        self.subscribers.setdefault(key, set()).add(component.root)
        if host is not None:
            results = []
            for root, values in self.resources.get(key, {}).items():
                if root.component.host is host:
                    results.extend(values)
        else:
            results = flatten(self.resources.get(key, {}).values())
        return results

    def reset_component_resources(self, root):
        # XXX I smell a potential optimization/blocker here: if we
        # reset the same resources that are provided again then we
        # don't have to retry the dependent components. This would
        # allow us to converge on circular dependencies if we do
        # establish an equilibrium at some point.
        for key, resources in self.resources.items():
            if root in resources:
                del resources[root]
                self.pending_dependencies.update(self.subscribers[key])

    @property
    def unused(self):
        return set(self.resources) - set(self.subscribers)

    @property
    def unsatisfied(self):
        return set(self.subscribers) - set(self.resources)

    @property
    def unsatisfied_components(self):
        components = set()
        for resource in self.unsatisfied:
            components.update(self.subscribers[resource])
        return components


class Environment(object):
    """An environment assigns components to hosts and provides
    environment-specific configuration for components.
    """

    service_user = None
    host_domain = None
    branch = u'default'
    platform = None

    def __init__(self, name, service):
        self.name = name
        self.service = service
        self.hosts = {}
        self.resources = Resources()

    def from_config(self, config):
        """Pull options that come from cfg file out of `config` dict."""
        for key in ['service_user', 'host_domain', 'branch', 'platform']:
            if key in config:
                setattr(self, key, config[key])
        if self.service_user is None:
            self.service_user = pwd.getpwuid(os.getuid()).pw_name

    def configure(self):
        """Configure all top-level components from all hosts.

        Monitor the dependencies between resources and try to converge
        to a stable order.

        """
        # Seed the working set with all components from all hosts
        working_set = set()
        for host in self.hosts.values():
            working_set.update(host.components)

        while working_set:
            last_working_set = working_set.copy()
            retry = set()
            exceptions = []
            self.resources.pending_dependencies.clear()

            for root in working_set:
                try:
                    root.component.prepare(self.service, self, root.host, root)
                except Exception, e:
                    exceptions.append(e)
                    retry.add(root)

            retry.update(self.resources.pending_dependencies)
            retry.update(self.resources.unsatisfied_components)

            if retry == last_working_set:
                # We did not manage to improve on our last working set, so we
                # give up.

                # Report all exceptions we got in the last run.
                for e in exceptions:
                    logger.exception(e)

                # If any resources were required but not provided at least
                # once we report this as well.
                if self.resources.unsatisfied:
                    logger.error('Unsatisfied resources: %s' %
                        ', '.join(self.resources.unsatisfied))

                raise NonConvergingWorkingSet(retry)

            working_set = retry

        # We managed to converge on a working set. However, some resource were
        # provided but never used. We're rather picky here and report this as
        # an error.
        if self.resources.unused:
            raise UnusedResource(self.resources.unused)

    def normalize_host_name(self, hostname):
        """Ensure the given host name is an FQDN for this environment."""
        if not self.host_domain:
            return hostname
        domain = self.host_domain
        return '%s.%s' % (hostname.rstrip(domain), domain)

    def get_host(self, hostname):
        return self.hosts[self.normalize_host_name(hostname)]
