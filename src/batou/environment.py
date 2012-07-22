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

    # Maps keys to root components that depend on the key.
    subscribers = None
    # Keeps track of root components that have not seen changes to a key they
    # have subscribed to when they were configured earlier..
    dirty_dependencies = None

    def __init__(self):
        self.resources = {}
        self.subscribers = {}
        self.dirty_dependencies = set()

    def provide(self, component, key, value):
        values = self.resources.setdefault(key, collections.defaultdict(list))
        values[component.root].append(value)
        self.dirty_dependencies.update(self.subscribers.get(key, ()))

    def get(self, key, host=None):
        """Return resource values without recording a dependency."""
        if host is not None:
            results = []
            for root, values in self.resources.get(key, {}).items():
                if root.component.host is host:
                    results.extend(values)
        else:
            results = flatten(self.resources.get(key, {}).values())
        return results

    def require(self, component, key, host=None):
        """Return resource values and record component dependency."""
        self.subscribers.setdefault(key, set()).add(component.root)
        return self.get(key, host)

    def reset_component_resources(self, root):
        """Remove all resources that were provided by this root component."""
        # XXX I smell a potential optimization/blocker here: if we
        # reset the same resources that are provided again then we
        # don't have to retry the dependent components. This would
        # allow us to converge on circular dependencies if we do
        # establish an equilibrium at some point.
        for key, resources in self.resources.items():
            if root not in resources:
                continue
            del resources[root]
            # Removing this resource requires invalidating components that
            # depend on this resource and have already been configured so we
            # need to mark them as dirty.
            if key in self.subscribers:
                self.dirty_dependencies.update(self.subscribers[key])

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
        # A mapping of overriding values that can be set on the root
        # components.
        self.overrides = {}

    def from_config(self, config):
        """Pull options that come from cfg file out of `config` dict."""
        for key in ['service_user', 'host_domain', 'branch', 'platform']:
            if key in config:
                setattr(self, key, config[key])
        if self.service_user is None:
            self.service_user = pwd.getpwuid(os.getuid()).pw_name
        if self.platform is None and self.host_domain:
            self.platform = self.host_domain

    def configure(self):
        """Configure all top-level components from all hosts.

        Monitor the dependencies between resources and try to converge
        to a stable order.

        """
        # This keeps track of the order which we used to successfully
        # configure all components.
        self.ordered_components = []
        # Seed the working set with all components from all hosts
        working_set = set()
        for host in self.hosts.values():
            working_set.update(host.components)

        while working_set:
            last_working_set = working_set.copy()
            retry = set()
            exceptions = []
            self.resources.dirty_dependencies.clear()

            for root in working_set:
                try:
                    if root.name in self.overrides:
                        root.component.__dict__.update(
                            self.overrides[root.name])
                    self.resources.reset_component_resources(root)
                    root.component.prepare(self.service, self, root.host, root)
                except Exception, e:
                    exceptions.append(e)
                    retry.add(root)
                # We prepared/configured this component successfully and take
                # note of the order. However: if it was run successfully
                # before then we prefer running it later.
                if root in self.ordered_components:
                    self.ordered_components.remove(root)
                self.ordered_components.append(root)

            retry.update(self.resources.dirty_dependencies)
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
        if not self.host_domain or hostname.endswith(self.host_domain):
            return hostname
        else:
            return '%s.%s' % (hostname, self.host_domain)

    def get_host(self, hostname):
        return self.hosts[self.normalize_host_name(hostname)]
