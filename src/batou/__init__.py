# This code must not cause non-stdlib imports to support self-bootstrapping.
from ._output import output
import os.path
import traceback

__version__ = open(os.path.dirname(__file__) + '/version.txt').read().strip()


class FileLockedError(Exception):
    """A file is already locked and we do not want to block."""

    def __init__(self, filename):
        self.filename = filename


class UpdateNeeded(AssertionError):
    """A component requires an update."""


class ConfigurationError(Exception):
    """Indicates that an environment could not be configured successfully."""

    @property
    def sort_key(self):
        return (0, self.message)

    def __init__(self, message, component=None):
        self.message = message
        self.component = component

    def report(self):
        if self.component:
            message = '{}@{}: {}'.format(
                self.component.root.name,
                self.component.root.host.name,
                self.message)
        else:
            message = self.message
        output.error(message)


class ConversionError(ConfigurationError):
    """An override attribute could not be converted properly."""

    @property
    def sort_key(self):
        return (1, self.component.root.host.name,
                self.component._breadcrumbs, self.key)

    def __init__(self, component, key, value, conversion, error):
        self.component = component
        self.key = key
        self.value = value
        self.conversion = conversion
        self.error = error

    def report(self):
        output.error('Failed override attribute conversion')
        output.tabular(
            'Host', self.component.root.host.name,
            red=True)
        output.tabular(
            'Attribute',
            '{}.{}'.format(
                self.component._breadcrumbs,
                self.key),
            red=True)
        output.tabular('Conversion',
                       '{}({})'.format(self.conversion.__name__,
                                       repr(self.value)),
                       red=True)
        # TODO provide traceback in debug output
        output.tabular('Error', str(self.error), red=True)


class SilentConfigurationError(Exception):
    """These are exceptions that will be reported by other exceptions.

    They basically only influence control flow during configuration and
    are manually placed to avoid double reporting.

    """


class MissingOverrideAttributes(ConfigurationError):

    @property
    def sort_key(self):
        return (3, self.component.root.host.name,
                self.component._breadcrumbs)

    def __init__(self, component, attributes):
        self.component = component
        self.attributes = attributes

    def report(self):
        output.error('Overrides for undefined attributes')
        output.tabular(
            'Host', self.component.root.host.name,
            red=True)
        output.tabular(
            'Component',
            self.component._breadcrumbs,
            red=True)
        output.tabular(
            'Attributes',
            ', '.join(self.attributes),
            red=True)

        # TODO point to specific line in secrets or environments
        # cfg file and show context


class DuplicateComponent(ConfigurationError):

    @property
    def sort_key(self):
        return (2, self.a.name)

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def report(self):
        output.error('Duplicate component "{}"'.format(self.a.name))
        output.tabular('Occurence', self.a.filename)
        output.tabular('Occurence', self.b.filename)


class UnknownComponentConfigurationError(ConfigurationError):
    """An unknown error occured while configuring a component."""

    @property
    def sort_key(self):
        return (4, self.root.host.name, 2)

    def __init__(self, root, exception, tb):
        self.root = root
        self.exception = exception
        stack = traceback.extract_tb(tb)
        from batou import environment, component
        while True:
            # Delete remoting-internal stack frames.'
            line = stack.pop(0)
            if line[0] in ['<string>', '<remote exec>',
                           environment.__file__.rstrip('c'),
                           component.__file__.rstrip('c')]:
                continue
            stack.insert(0, line)
            break
        self.traceback = ''.join(traceback.format_list(stack))

    def report(self):
        output.error(repr(self.exception))
        output.annotate(
            "This /might/ be a batou bug. Please consider reporting it.\n",
            red=True)
        output.tabular(
            "Host", self.root.host.name, red=True)
        output.tabular(
            "Component", self.root.name + '\n', red=True)
        output.annotate('Traceback (simplified, most recent call last):',
                        red=True)
        output.annotate(self.traceback, red=True)


class UnusedResources(ConfigurationError):
    """Some provided resources were never used."""

    @property
    def sort_key(self):
        return (5, 'unused')

    def __init__(self, resources):
        self.resources = resources

    def report(self):
        output.error("Unused provided resources")
        for key in sorted(self.resources):
            for component, value in list(self.resources[key].items()):
                output.line(
                    '    Resource "{}" provided by {} with value {}'.format(
                        key, component.name, value),
                    red=True)


class UnsatisfiedResources(ConfigurationError):
    """Some required resources were never provided."""

    @property
    def sort_key(self):
        return (6, 'unsatisfied')

    def __init__(self, resources):
        self.resources = resources

    def report(self):
        output.error("Unsatisfied resource requirements")
        for key in sorted(self.resources):
            output.line('    Resource "{}" required by {}'.format(
                key, ','.join(r.name for r in self.resources[key])),
                red=True)


class MissingEnvironment(ConfigurationError):
    """The specified environment does not exist."""

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, environment):
        self.environment = environment

    def report(self):
        output.error("Missing environment")
        output.tabular('Environment', self.environment.name, red=True)


class ComponentLoadingError(ConfigurationError):
    """The specified component file failed to load."""

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, filename, exception):
        self.filename = filename
        self.exception = exception

    def report(self):
        output.error("Failed loading component file")
        output.tabular("File", self.filename, red=True)
        output.tabular("Exception", str(self.exception), red=True)
        # TODO provide traceback in debug output


class MissingComponent(ConfigurationError):
    """The specified environment does not exist."""

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, component, hostname):
        self.component = component
        self.hostname = hostname

    def report(self):
        output.error("Missing component")
        output.tabular('Component', self.component, red=True)
        output.tabular('Host', self.hostname, red=True)


class SuperfluousSection(ConfigurationError):
    """A superfluous section was found in the environment
    configuration file."""

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, section):
        self.section = section

    def report(self):
        output.error("Superfluous section in environment configuration")
        output.tabular("Section", self.section, red=True)
        # TODO provide location and context in debug output


class SuperfluousComponentSection(ConfigurationError):
    """A component section was found in the environment
    but no associated component is known."""

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, component):
        self.component = component

    def report(self):
        output.error("Override section for unknown component found")
        output.tabular("Component", self.component, red=True)
        # TODO provide traceback in debug output


class SuperfluousSecretsSection(ConfigurationError):
    """A component section was found in the secrets
    but no associated component is known."""

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, component):
        self.component = component

    def report(self):
        output.error("Secrets section for unknown component found")
        output.tabular("Component", self.component, red=True)
        # TODO provide traceback in debug output


class CycleErrorDetected(ConfigurationError):
    """We think we found a cycle in the component dependencies.
    """

    @property
    def sort_key(self):
        return (99, )

    def __init__(self, error):
        self.error = error

    def report(self):
        output.error("Found dependency cycle")
        output.annotate(str(self.error), red=True)
        # TODO provide traceback in debug output


class NonConvergingWorkingSet(ConfigurationError):
    """A working set did not converge."""

    @property
    def sort_key(self):
        return (100, )

    def __init__(self, roots):
        self.roots = roots

    def report(self):
        # TODO show this last or first, but not in the middle
        # of everything
        output.error("{} remaining unconfigured component(s)".format(
                     len(self.roots)))
        # TODO show all incl. their host name in -vv or so
        # output.annotate(', '.join(c.name for c in self.roots))


class DeploymentError(Exception):
    """Indicates that a deployment failed.."""

    @property
    def sort_key(self):
        return (200, )

    def report(self):
        pass


class RepositoryDifferentError(DeploymentError):
    """The repository on the remote side is different."""

    @property
    def sort_key(self):
        return (150, )

    def __init__(self, local, remote):
        self.local = local
        self.remote = remote

    def report(self):
        output.error(
            "The remote working copy is based on a different revision. "
            "Maybe you tried to deploy from the wrong branch.")
        output.tabular("Local", self.local, red=True)
        output.tabular("Remote", self.remote, red=True)


class DuplicateHostError(ConfigurationError):

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, hostname):
        self.hostname = hostname

    def report(self):
        output.error("Duplicate definition of host: {}".format(self.hostname))


class InvalidIPAddressError(ConfigurationError):

    @property
    def sort_key(self):
        return (0, )

    def __init__(self, address):
        self.address = address

    def report(self):
        output.error("Not a valid IP address: {}".format(self.address))
