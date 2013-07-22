from .component import load_components_from_file
from .host import Host
from .resources import Resources
from .secrets import add_secrets_to_environment_override
from batou import NonConvergingWorkingSet, UnusedResource
from batou.component import RootComponent
from batou.utils import flatten, revert_graph, topological_sort
from collections import defaultdict
import batou.c
import batou.vfs
import configobj
import glob
import logging
import os
import os.path
import pwd


logger = logging.getLogger(__name__)


class Environment(object):
    """An environment assigns components to hosts and provides
    environment-specific configuration for components.
    """

    service_user = None
    host_domain = None
    branch = u'default'
    platform = None
    vfs_sandbox = None

    def __init__(self, name):
        self.name = name
        self.hosts = {}
        self.resources = Resources()
        self.overrides = {}

        # These are the component classes, decorated with their 
        # name.
        self.components = {}
        # These are the components assigned to hosts.
        self.root_components = []

    # XXX Extract
    def load(self):
        # Scan all components
        for filename in glob.glob('components/*/component.py'):
            self.components.update(load_components_from_file(filename))

        # Load environment configuration
        config_file = 'environments/{}.cfg'.format(self.name)
        if not os.path.isfile(config_file):
            raise ValueError('No such environment "{}"'.format(self.name))

        config = configobj.ConfigObj(config_file)

        if 'environment' in config:
            for key in ['service_user', 'host_domain', 'branch', 'platform']:
                if key not in config:
                    configure
                if getattr(self, key) is not None:
                    # Support early overrides from e.g. the CLI or tests
                    continue
                setattr(self, key, config[key])

        if self.service_user is None:
            self.service_user = pwd.getpwuid(os.getuid()).pw_name

        if self.platform is None and self.host_domain:
            self.platform = self.host_domain

        if 'vfs' in config:
            sandbox = config['vfs']['sandbox']
            sandbox = getattr(batou.vfs, sandbox)(self, config['vfs'])
            self.vfs_sandbox = sandbox

        for hostname in config['hosts']:
            fqdn = self.normalize_host_name(hostname)
            self.hosts[fqdn] = host = Host(fqdn)
            # load components for host
            for name, features in parse_host_components(
                    config['hosts'].as_list(hostname)).items():
                root = RootComponent(self.components[name])
                root.name = name
                root.host = host
                root.features = features
                self.root_components.append(root)

        # load overrides
        for section in config:
            if not section.startswith('component:'):
                continue
            root_name = section.replace('component:', '')
            self.overrides.setdefault(root_name, {})
            self.overrides[root_name].update(config[section])

    def configure(self):
        """Configure all root components.

        Monitor the dependencies between resources and try to reach a stable
        order.

        """
        working_set = set(self.root_components)

        previous_working_sets = []
        while working_set:
            previous_working_sets.append(working_set.copy())
            retry = set()
            exceptions = []
            self.resources.dirty_dependencies.clear()

            for root in working_set:
                try:
                    self.resources.reset_component_resources(root)
                    root.component = root.factory()
                    root.component.prepare(self, root.host, root) 
                except Exception, e:
                    exceptions.append(e)
                    retry.add(root)
                    continue

            retry.update(self.resources.dirty_dependencies)
            retry.update(self.resources.unsatisfied_components)

            # Try to find a valid order of the components. If we can't then we
            # have detected a dependency cycle and need to stop.

            self.roots_in_order()

            if (retry in previous_working_sets):
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

    def load_secrets(self):
        add_secrets_to_environment_override(self)

    def roots_in_order(self, host=None):
        """Return a list of root components sorted by their resource dependencies,
        filtered by host if specified.

        Raises ValueError if component dependencies have cycles.

        """
        dependencies = self.resources.get_dependency_graph()
        # Complete the graph with components that do not have any dependencies
        # (yet)
        for root in self.root_components:
            if root not in dependencies:
                dependencies[root] = set()
        roots = topological_sort(revert_graph(dependencies))
        if host is not None:
            host = self.get_host(host)
            roots = filter(lambda x:x.host is host, roots)
        return roots

    def normalize_host_name(self, hostname):
        """Ensure the given host name is an FQDN for this environment."""
        if not self.host_domain or hostname.endswith(self.host_domain):
            return hostname
        else:
            return '%s.%s' % (hostname, self.host_domain)

    def get_host(self, hostname):
        return self.hosts[self.normalize_host_name(hostname)]

    def map(self, path):
        if self.vfs_sandbox:
            return self.vfs_sandbox.map(path)
        return path


def parse_host_components(components):
    """Parse a component list as given in an environment config for a host
    into a mapping of compoment -> features.

    Expected syntax:

    component[:feature], component[:feature]

    """
    result = {}
    for name in components:
        name = name.strip()
        if ':' in name:
            name, feature = name.split(':', 1)
        else:
            feature = None
        result.setdefault(name, [])
        if feature:
            result[name].append(feature)
    return result
