from .component import load_components_from_file
from .host import Host
from .resources import Resources
from .secrets import add_secrets_to_environment_override
from ConfigParser import RawConfigParser
from batou import NonConvergingWorkingSet, UnusedResource
from batou.component import RootComponent
from batou.utils import revert_graph, topological_sort
import batou.c
import batou.vfs
import glob
import logging
import os
import os.path
import pwd
import sys


logger = logging.getLogger(__name__)


class ConfigSection(dict):
    def as_list(self, option):
        result = self[option]
        if ',' in result:
            result = [x.strip() for x in result.split(',')]
        elif '\n' in result:
            result = (x.strip() for x in result.split('\n'))
            result = [x for x in result if x]
        else:
            result = [result]
        return result


class Config(object):
    def __init__(self, path):
        config = RawConfigParser()
        config.optionxform = lambda s: s
        config.read(path)
        self.config = config

    def __contains__(self, section):
        return self.config.has_section(section)

    def __getitem__(self, section):
        if section not in self:
            raise KeyError(section)
        return ConfigSection(
            (x, self.config.get(section, x))
            for x in self.config.options(section))

    def __iter__(self):
        return iter(self.config.sections())

    def get(self, section, default=None):
        try:
            return self[section]
        except KeyError:
            return default


class Environment(object):
    """An environment assigns components to hosts and provides
    environment-specific configuration for components.
    """

    service_user = None
    host_domain = None
    branch = None
    connect_method = None
    update_method = None
    platform = None
    vfs_sandbox = None
    timeout = None
    target_directory = None

    def __init__(self, name, basedir='.'):
        self.name = name
        self.hosts = {}
        self.resources = Resources()
        self.overrides = {}

        # These are the component classes, decorated with their
        # name.
        self.components = {}
        # These are the components assigned to hosts.
        self.root_components = []

        self.base_dir = os.path.abspath(basedir)
        self.workdir_base = os.path.join(self.base_dir, 'work')

    def load(self):
        # Scan all components
        for filename in sorted(glob.glob(
                os.path.join(self.base_dir, 'components/*/component.py'))):
            self.components.update(load_components_from_file(filename))

        # Load environment configuration
        config_file = os.path.join(
            self.base_dir, 'environments/{}.cfg'.format(self.name))
        if not os.path.isfile(config_file):
            raise ValueError('No such environment "{}"'.format(self.name))

        config = Config(config_file)

        self.load_environment(config)
        for hostname in config.get('hosts', {}):
            components = parse_host_components(
                config['hosts'].as_list(hostname))
            for component, features in components.items():
                self.add_root(component, hostname, features)

        # load overrides
        for section in config:
            if not section.startswith('component:'):
                continue
            root_name = section.replace('component:', '')
            self.overrides.setdefault(root_name, {})
            self.overrides[root_name].update(config[section])

    def load_secrets(self):
        add_secrets_to_environment_override(self)

    def load_environment(self, config):
        environment = config.get('environment', {})
        for key in ['service_user', 'host_domain', 'target_directory',
                    'connect_method', 'update_method', 'branch', 'platform',
                    'timeout']:
            if key not in environment:
                continue
            if getattr(self, key) is not None:
                # Avoid overriding early changes that have already been
                # applied, e.g. by tests.
                continue
            setattr(self, key, environment[key])

        self._set_defaults()

        if 'vfs' in config:
            sandbox = config['vfs']['sandbox']
            sandbox = getattr(batou.vfs, sandbox)(self, config['vfs'])
            self.vfs_sandbox = sandbox

    def _set_defaults(self):
        if self.branch is None:
            self.branch = u'default'
        if self.update_method is None:
            self.update_method = 'pull'
        if self.connect_method is None:
            self.connect_method = 'ssh'

        if self.service_user is None:
            self.service_user = pwd.getpwuid(os.getuid()).pw_name

        if self.target_directory is None:
            self.target_directory = '~/deployment'

        if self.platform is None and self.host_domain:
            self.platform = self.host_domain

        if self.timeout is None:
            self.timeout = 3
        else:
            self.timeout = int(self.timeout)

    # API to instrument environment config loading

    def add_host(self, hostname):
        fqdn = self.normalize_host_name(hostname)
        if fqdn not in self.hosts:
            self.hosts[fqdn] = Host(fqdn)
        return self.hosts[fqdn]

    def add_root(self, component_name, hostname, features=()):
        host = self.add_host(hostname)
        root = RootComponent(component_name, self, host, features)
        self.root_components.append(root)
        return root

    def get_root(self, component_name, hostname):
        host = self.add_host(hostname)
        for root in self.root_components:
            if root.host == host and root.name == component_name:
                return root
        raise KeyError("Component {} not configured for host {}".format(
            component_name, hostname))

    # Deployment API (implements the configure-verify-update cycle)

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
                    root.prepare()
                except Exception:
                    exceptions.append((root, sys.exc_info()))
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
                for root, e in exceptions:
                    logger.error('', exc_info=e)

                # If any resources were required but not provided at least
                # once we report this as well.
                if self.resources.unsatisfied:
                    logger.error('Unsatisfied resources: %s' %
                                 ', '.join(self.resources.unsatisfied))

                if exceptions:
                    logger.error('\nThe following exceptions occurred '
                                 '(see tracebacks above):')
                for root, e in exceptions:
                    logger.error('%s: %r', root.name, e[1])
                raise NonConvergingWorkingSet(retry)

            working_set = retry

        # We managed to converge on a working set. However, some resource were
        # provided but never used. We're rather picky here and report this as
        # an error.
        if self.resources.unused:
            raise UnusedResource(self.resources.unused)

    def roots_in_order(self, host=None):
        """Return a list of root components sorted by their resource
        dependencies, filtered by host if specified.

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
            roots = filter(lambda x: x.host is host, roots)
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
