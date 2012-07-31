from batou import NonConvergingWorkingSet, UnusedResource
from batou.utils import flatten
import collections
import json
import logging
import os
import pwd

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

    def provide(self, root, key, value):
        try:
            json.dumps(value)
        except TypeError:
            raise TypeError('Resource values must be "simple" types.')
        values = self.resources.setdefault(key, collections.defaultdict(list))
        values[root].append(value)

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

    def require(self, root, key, host=None):
        """Return resource values and record component dependency."""
        self.subscribers.setdefault(key, set()).add(root)
        return self.get(key, host)

    def reset_component_resources(self, root):
        """Move all resources aside that were provided by this component."""
        for key, resources in self.resources.items():
            if root not in resources:
                continue
            del resources[root]

    def snapshot(self):
        """Take a snapshot of the current state of the resources.

        Returns a snapshot object. Snapshot objects can be tested for equality.

        """
        return json.dumps(self.flat_resources)

    @property
    def flat_resources(self):
        flat = {}
        for key in self.resources:
            flat[key] = self.get(key)
        return flat

    def dependent_components(self, root):
        # find all keys provided by this component
        keys = set()
        for key, resources in self.resources.items():
            if root in resources:
                keys.add(key)

        subscribers = set()
        for key in keys:
            subscribers.update(self.subscribers.get(key, []))

        return subscribers

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

            resources_before_workingset = self.resources.snapshot()

            for root in working_set:
                resources_before = self.resources.snapshot()
                subscribers = self.resources.dependent_components(root)
                try:
                    root.prepare()
                except Exception, e:
                    exceptions.append(e)
                    retry.add(root)
                    continue

                resources_after = self.resources.snapshot()
                if resources_before != resources_after:
                    retry.update(subscribers)
                    retry.update(self.resources.dependent_components(root))

                # We prepared/configured this component successfully and take
                # note of the order. However: if it was run successfully
                # before then we prefer running it later.
                if root in self.ordered_components:
                    self.ordered_components.remove(root)
                self.ordered_components.append(root)

            retry.update(self.resources.dirty_dependencies)
            retry.update(self.resources.unsatisfied_components)

            resources_after_workingset = self.resources.snapshot()

            if (retry == last_working_set and
                resources_after_workingset == resources_before_workingset):
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
