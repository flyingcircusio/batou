from batou.utils import flatten
from collections import defaultdict
import logging


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

    # A "strict" dependency means that it's not OK to have this dependency
    # unsatisfied and requires at least one value.

    # A reverse dependency means that the dependency map will reverse the root
    # components order: "require before provide" instead of the default
    # "provide before require"

    # {key: [(root, strict, host, reverse),
    #        (root, strict, host, reverse), ...]}
    subscribers = None
    # Keeps track of root components that have not seen changes to a key they
    # have subscribed to when they were configured earlier..
    dirty_dependencies = None

    # {key: {host: [values]}}
    resources = None

    def __init__(self):
        self.resources = {}
        self.subscribers = {}
        self.dirty_dependencies = set()

    def _subscribers(self, key, host):
        return [root for root, strict, host_, reverse
                in self._subscriptions(key, host)]

    def _subscriptions(self, key, host):
        return [(root, strict, host_, reverse)
                for root, strict, host_, reverse
                in self.subscribers.get(key, ())
                if host_ is None or host is None or host_ is host]

    @property
    def strict_subscribers(self):
        for key, subscribers in self.subscribers.items():
            if any(strict for root, strict, host, reverse in subscribers):
                yield key

    def provide(self, root, key, value):
        values = self.resources.setdefault(key, defaultdict(list))
        values[root].append(value)
        self.dirty_dependencies.update(self._subscribers(key, root.host))

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

    def require(self, root, key, host=None, strict=True, reverse=False):
        """Return resource values and record component dependency."""
        self.subscribers.setdefault(key, set()).add(
            (root, strict, host, reverse))
        return self.get(key, host)

    def reset_component_resources(self, root):
        """Move all resources aside that were provided by this component."""
        for key, resources in self.resources.items():
            if root not in resources:
                continue
            del resources[root]
            # Removing this resource requires invalidating components that
            # depend on this resource and have already been configured so we
            # need to mark them as dirty.
            self.dirty_dependencies.update(self._subscribers(key, root.host))

    def copy_resources(self):
        # A "one level deep" copy of the resources dict to be used by the
        # `unused` property.
        resources = {}
        for key, providers in self.resources.items():
            resources[key] = dict(providers)
        return resources

    @property
    def unused(self):
        # XXX. Gah. This makes my head explode: we need to take the 'host'
        # filter into account whether some of the values provided where never
        # used.
        resources = self.copy_resources()
        for key, subscribers in self.subscribers.items():
            if key not in resources:
                continue
            for root, strict, host, reverse in subscribers:
                if host is None:
                    del resources[key]
                    break
                for resource_root in list(resources[key]):
                    if resource_root.host is host:
                        del resources[key][resource_root]
                        if not resources[key]:
                            del resources[key]
                            break
                if not key in resources:
                    break
        return resources

    @property
    def unsatisfied(self):
        return set(self.strict_subscribers) - set(self.resources)

    @property
    def unsatisfied_components(self):
        components = set()
        for resource in self.unsatisfied:
            components.update(self._subscribers(resource, None))
        return components

    def get_dependency_graph(self):
        """Return a dependency graph as a dict of lists:

        {component: [dependency1, dependency2],
         ...}

        """
        graph = defaultdict(set)
        for key, providers in self.resources.items():
            for subscriber, _, _, reverse in self._subscriptions(key, None):
                if reverse:
                    for provider in providers:
                        graph[provider].add(subscriber)
                else:
                    graph[subscriber].update(providers)
        return graph
