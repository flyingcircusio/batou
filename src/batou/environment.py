from .component import load_components_from_file
from .host import LocalHost, RemoteHost
from .resources import Resources
from .secrets import add_secrets_to_environment_override
from batou import MissingEnvironment, ComponentLoadingError, SuperfluousSection
from batou import MissingComponent
from batou import NonConvergingWorkingSet, UnusedResources, ConfigurationError
from batou import SuperfluousComponentSection, CycleErrorDetected
from batou import UnknownComponentConfigurationError, UnsatisfiedResources
from batou._output import output
from batou.component import RootComponent
from batou.repository import Repository
from batou.utils import cmd
from batou.utils import revert_graph, topological_sort, CycleError
from ConfigParser import RawConfigParser
import batou.c
import batou.vfs
import glob
import os
import os.path
import pwd
import sys


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

    repository_url = None
    version = None
    develop = None

    def __init__(self, name, timeout=None, platform=None, basedir='.'):
        self.name = name
        self.hosts = {}
        self.resources = Resources()
        self.overrides = {}
        self.exceptions = []
        self.timeout = timeout
        self.platform = platform

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
            try:
                self.components.update(load_components_from_file(filename))
            except Exception as e:
                self.exceptions.append(ComponentLoadingError(filename, e))

        # Load environment configuration
        config_file = os.path.join(
            self.base_dir, 'environments/{}.cfg'.format(self.name))
        if not os.path.isfile(config_file):
            raise MissingEnvironment(self)

        config = Config(config_file)

        self.load_environment(config)
        for hostname in config.get('hosts', {}):
            components = parse_host_components(
                config['hosts'].as_list(hostname))
            for component, features in components.items():
                try:
                    self.add_root(component, hostname, features)
                except KeyError as e:
                    self.exceptions.append(
                        MissingComponent(component, hostname))

        # load overrides
        for section in config:
            if not section.startswith('component:'):
                if section not in ['hosts', 'environment', 'vfs']:
                    self.exceptions.append(SuperfluousSection(section))
                continue
            root_name = section.replace('component:', '')
            if root_name not in self.components:
                self.exceptions.append(SuperfluousComponentSection(root_name))
                continue
            self.overrides.setdefault(root_name, {})
            self.overrides[root_name].update(config[section])

        self.repository = Repository.from_environment(self)

        # The deployment base is the path relative to the
        # repository where batou is located (with ./batou,
        # ./environments, and ./components)
        self.deployment_base = os.path.relpath(
            self.base_dir, self.repository.root)

    def load_secrets(self):
        add_secrets_to_environment_override(self)

    def load_environment(self, config):
        environment = config.get('environment', {})
        for key in ['service_user', 'host_domain', 'target_directory',
                    'connect_method', 'update_method', 'branch',
                    'platform', 'timeout', 'develop', 'repository_url']:
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
        if self.update_method is None:
            self.update_method = 'rsync'
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

        if self.version is None:
            self.version = os.environ.get('BATOU_VERSION')

        if self.develop is None:
            self.develop = os.environ.get('BATOU_DEVELOP')

    # API to instrument environment config loading

    def add_host(self, hostname):
        fqdn = self.normalize_host_name(hostname)
        if fqdn not in self.hosts:
            if self.connect_method == 'local':
                self.hosts[fqdn] = LocalHost(fqdn, self)
            else:
                self.hosts[fqdn] = RemoteHost(fqdn, self)
        return self.hosts[fqdn]

    def add_root(self, component_name, hostname, features=()):
        host = self.add_host(hostname)
        compdef = self.components[component_name]
        root = RootComponent(
            name=compdef.name,
            environment=self,
            host=host,
            features=features,
            factory=compdef.factory,
            defdir=compdef.defdir,
            workdir=os.path.join(self.workdir_base, compdef.name))
        self.root_components.append(root)
        return root

    def get_root(self, component_name, hostname):
        host = self.add_host(hostname)
        for root in self.root_components:
            if root.host == host and root.name == component_name:
                return root
        raise KeyError("Component {} not configured for host {}".format(
            component_name, hostname))

    def prepare_connect(self):
        if self.deployment.fast:
            return
        if self.connect_method == 'vagrant':
            output.step("vagrant", "Ensuring machines are up ...")
            cmd('vagrant up')

    # Deployment API (implements the configure-verify-update cycle)

    def configure(self):
        """Configure all root components.

        Monitor the dependencies between resources and try to reach a stable
        order.

        """
        working_set = set(self.root_components)

        previous_working_sets = []
        exceptions = []

        while working_set:
            exceptions = []
            previous_working_sets.append(working_set.copy())
            retry = set()
            self.resources.dirty_dependencies.clear()

            for root in working_set:
                try:
                    self.resources.reset_component_resources(root)
                    root.overrides = self.overrides.get(root.name, {})
                    root.prepare()
                except ConfigurationError as e:
                    # A known exception which we can report gracefully later.
                    exceptions.append(e)
                    retry.add(root)
                except Exception as e:
                    # An unknown exception which we have to work harder
                    # to report gracefully.
                    ex_type, ex, tb = sys.exc_info()
                    exceptions.append(
                        UnknownComponentConfigurationError(root, e, tb))
                    retry.add(root)

            retry.update(self.resources.dirty_dependencies)
            retry.update(self.resources.unsatisfied_components)

            # Try to find a valid order of the components. If we can't then we
            # have detected a dependency cycle and need to stop.

            try:
                self.roots_in_order()
            except CycleError as e:
                exceptions.append(CycleErrorDetected(e))

            if (retry in previous_working_sets):
                # If any resources were required, now is the time to report
                # them.
                if self.resources.unsatisfied:
                    exceptions.append(UnsatisfiedResources(
                        self.resources.unsatisfied))

                # We did not manage to improve on our last working set, so we
                # give up.
                exceptions.append(NonConvergingWorkingSet(retry))
                break

            working_set = retry

        # We managed to converge on a working set. However, some resource were
        # provided but never used. We're rather picky here and report this as
        # an error.
        if self.resources.unused:
            exceptions.append(UnusedResources(self.resources.unused))

        self.exceptions.extend(exceptions)
        if self.exceptions:
            # We just raise here to support a reasonable flow
            # for our caller. We expect him to look at our exceptions
            # attribute anyway.
            raise self.exceptions[0]

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
