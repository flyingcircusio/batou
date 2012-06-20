# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .component import load_components_from_file
from .host import Host
from .environment import Environment
import batou.utils
import ConfigParser
import glob
import os
import os.path


class ServiceConfig(object):
    """A service configuration.

    Handles the on-disk format of service, component, and environment
    parameters.

    Two phases: scan, configure

    Scan -- discovers all elements (environments, hosts, components) but
    doesn't create an actual configuration

    Configure -- turns all discovered elements into an actual
    configuration that can be deployed.

    This two-phase approach is required to allow better instrumentation
    of the loading process while integrating with Fabric.
    """

    platform = None     # XXX overridden via CLI

    def __init__(self, basedir, environments=[]):
        self.environments = set(environments)
        self.basedir = os.path.abspath(basedir)
        if not os.path.exists(self.basedir):
            raise IOError('No such file or directory: %r' % self.basedir)
        self.component_pattern = (self.basedir + '/components/*/component.py')
        self.environment_pattern = (self.basedir + '/environments/*.cfg')

        service = Service()
        service.base = self.basedir
        self.service = service

    def scan(self):
        self.scan_components()
        self.scan_environments()

    def scan_components(self):
        for filename in glob.glob(self.component_pattern):
            for factory in load_components_from_file(filename):
                self.service.components[factory.name] = factory

    def scan_environments(self):
        """Set up basic environment objects for all configs found."""
        existing_environments = glob.glob(self.environment_pattern)
        for pattern in [self.service.base + '/environments/', '.cfg']:
            existing_environments = map(lambda x: x.replace(pattern, ''),
                                           existing_environments)
        self.existing_environments = set(existing_environments)

        if self.environments:
            self.environments = self.existing_environments & self.environments
        else:
            self.environments = self.existing_environments
        for environment in self.environments:
            self.load_environment(environment)

    def load_environment(self, environment):
        """Instantiate environment object structure from config."""
        config = ConfigParser.SafeConfigParser()
        config.read('%s/environments/%s.cfg' % (
            self.service.base, environment))
        env = Environment(environment, self.service)
        env_config = {}
        if 'environment' in config.sections():
            env_config.update(dict(config.items('environment')))
        if self.platform is not None:
            env_config['platform'] = self.platform
        env.from_config(env_config)
        # load hosts
        for hostname in config.options('hosts'):
            fqdn = env.normalize_host_name(hostname)
            env.hosts[fqdn] = host = Host(fqdn, env)
            # load components for host
            for name, features in parse_host_components(
                    config.get('hosts', hostname)).items():
                host.add_component(name, features)
        self.service.environments[env.name] = env


def parse_host_components(components):
    """Parse a component list as given in an environment config for a host
    into a mapping of compoment -> features.

    Expected syntax:

    component[:feature], component[:feature]

    """
    result = {}
    for name in components.split(','):
        name = name.strip()
        if ':' in name:
            name, feature = name.split(':', 1)
        else:
            feature = None
        result.setdefault(name, [])
        if feature:
            result[name].append(feature)
    return result


class Service(object):

    base = None

    def __init__(self):
        self.components = {}
        self.environments = {}
