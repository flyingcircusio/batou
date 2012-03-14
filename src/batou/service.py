# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .component import Component
from .host import Host
from batou import Environment
import batou.utils
import collections
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
            for factory, name in Component.from_file(filename):
                self.service.components[name] = factory

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
        try:
            env = Environment(environment, self.service)
            env.configure(dict(config.items('environment')))
        except Exception, e:
            print "Problem loading environment %s: %r (ignored)" % (
                environment, e)
            return
        self.load_hosts(env, config)
        self.service.environments[env.name] = env

    def load_hosts(self, env, config):
        for hostname in config.options('hosts'):
            fqdn = env.normalize_host_name(hostname)
            env.hosts[fqdn] = host = Host(fqdn, env)
            # load components for host
            components = collections.OrderedDict()
            for component in batou.utils.string_list(
                    config.get('hosts', hostname)):
                feature = None
                if ':' in component:
                    component, feature = component.split(':')
                components.setdefault(component, [])
                if feature:
                    components[component].append(feature)
            self.assemble_host_components(host, config, components)

    def assemble_host_components(self, host, config, components):
        """Create all components for a host and do the wire-up."""
        for component, features in components.items():
            factory = self.service.components[component]
            component_config = {}
            if config.has_section('component:%s' % component):
                component_config.update(
                    dict(config.items('component:%s' % component)))
            if not features:
                features = factory.features
            host.components.append(factory(
                component, host, features, component_config))

    def configure_components(self, environment):
        for host in environment.hosts.values():
            for component in host.components:
                component._configure()


class Service(object):

    base = None

    def __init__(self):
        self.components = {}
        self.environments = {}
