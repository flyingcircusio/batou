# This code must not cause non-stdlib imports to support self-bootstrapping.
import os
import os.path
import traceback

from ._output import output

with open(os.path.dirname(__file__) + "/version.txt") as f:
    __version__ = f.read().strip()

# Configure `remote-pdb` to be used with `breakpoint()` in Python 3.7+:
os.environ['PYTHONBREAKPOINT'] = "remote_pdb.set_trace"
if not os.environ.get('REMOTE_PDB_HOST', None):
    os.environ['REMOTE_PDB_HOST'] = "127.0.0.1"
if not os.environ.get('REMOTE_PDB_PORT', None):
    os.environ['REMOTE_PDB_PORT'] = "4444"


class ReportingException(Exception):
    """Exceptions that support user-readable reporting."""

    def __str__(self):
        raise NotImplementedError()

    def report(self):
        raise NotImplementedError()


class FileLockedError(ReportingException):
    """A file is already locked and we do not want to block."""

    def __init__(self, filename):
        self.filename = filename

    def __str__(self):
        return "File already locked: {}".format(self.filename)

    def report(self):
        output.error(str(self))


class GPGCallError(ReportingException):
    """There was an error calling GPG on encrypted file."""

    def __init__(self, command, exitcode, output):
        self.command = ' '.join(command)
        self.exitcode = str(exitcode)
        self.output = output.decode('ascii', errors='replace')

    def __str__(self):
        return (f"Exitcode {self.exitcode} while calling: "
                f"{self.command}\n{self.output}")

    def report(self):
        output.error('Error while calling GPG')
        output.tabular('command', self.command, red=True)
        output.tabular('exit code', self.exitcode)
        output.tabular('message', self.output, separator=":\n")


class UpdateNeeded(AssertionError):
    """A component requires an update."""


class ConfigurationError(ReportingException):
    """Indicates that an environment could not be configured successfully."""

    @property
    def sort_key(self):
        return (0, self.message)

    def __init__(self, message, component=None):
        self.message = message
        self.component = component

    def __str__(self):
        return str(self.message)

    def report(self):
        message = self.message
        if self.component:
            message = "{}@{}: {}".format(self.component.root.name,
                                         self.component.root.host.name,
                                         message)
        output.error(message)


class ConversionError(ConfigurationError):
    """An override attribute could not be converted properly."""

    @property
    def sort_key(self):
        return (1, self.component.root.host.name, self.component._breadcrumbs,
                self.key)

    def __init__(self, component, key, value, conversion, error):
        self.component = component
        self.key = key
        self.value = value
        self.conversion = conversion
        self.error = error

    def __str__(self):
        return self.error

    def report(self):
        output.error("Failed override attribute conversion")
        output.tabular("Host", self.component.root.host.name, red=True)
        output.tabular(
            "Attribute",
            "{}.{}".format(self.component._breadcrumbs, self.key),
            red=True)
        output.tabular(
            "Conversion",
            "{}({})".format(self.conversion.__name__, repr(self.value)),
            red=True)
        # TODO provide traceback in debug output
        output.tabular("Error", str(self.error), red=True)


class SilentConfigurationError(Exception):
    """These are exceptions that will be reported by other exceptions.

    They basically only influence control flow during configuration and
    are manually placed to avoid double reporting.

    """


class MissingOverrideAttributes(ConfigurationError):

    @property
    def sort_key(self):
        return (3, self.component.root.host.name, self.component._breadcrumbs)

    def __init__(self, component, attributes):
        self.component = component
        self.attributes = attributes

    def __str__(self):
        return 'Overrides for undefined attributes ' + ','.join(
            self.attributes)

    def report(self):
        output.error("Overrides for undefined attributes")
        output.tabular("Host", self.component.root.host.name, red=True)
        output.tabular("Component", self.component._breadcrumbs, red=True)
        output.tabular("Attributes", ", ".join(self.attributes), red=True)

        # TODO point to specific line in secrets or environments
        # cfg file and show context


class DuplicateComponent(ConfigurationError):

    @property
    def sort_key(self):
        return (2, self.a.name)

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __str__(self):
        return 'Duplicate component: ' + self.a

    def report(self):
        output.error('Duplicate component "{}"'.format(self.a.name))
        output.tabular("Occurrence", self.a.filename)
        output.tabular("Occurrence", self.b.filename)


class DuplicateHostMapping(ConfigurationError):

    @property
    def sort_key(self):
        return (3, self.hostname, self.a, self.b)

    def __init__(self, hostname, a, b):
        self.hostname = hostname
        self.a = a
        self.b = b

    def __str__(self):
        return 'Duplicate host mapping: ' + self.hostname

    def report(self):
        output.error('Duplicate host mapping "{}"'.format(self.hostname))
        output.tabular("Mapping 1: ", self.a)
        output.tabular("Mapping 2: ", self.b)


class UnknownComponentConfigurationError(ConfigurationError):
    """An unknown error occured while configuring a component."""

    @property
    def sort_key(self):
        return (4, self.root.host.name, 2)

    def __init__(self, root, exception, tb):
        self.root = root
        self.exception = exception
        stack = traceback.extract_tb(tb)
        from batou import component, environment

        while True:
            # Delete remoting-internal stack frames.'
            line = stack.pop(0)
            if line[0] in [
                    "<string>", "<remote exec>",
                    environment.__file__.rstrip("c"),
                    component.__file__.rstrip("c")]:
                continue
            stack.insert(0, line)
            break
        self.traceback = "".join(traceback.format_list(stack))

    def __str__(self):
        return repr(self.exception)

    def report(self):
        output.error(repr(self.exception))
        output.annotate(
            "This /might/ be a batou bug. Please consider reporting it.\n",
            red=True)
        output.tabular("Host", self.root.host.name, red=True)
        output.tabular("Component", self.root.name + "\n", red=True)
        output.annotate(
            "Traceback (simplified, most recent call last):", red=True)
        output.annotate(self.traceback, red=True)


class UnusedResources(ConfigurationError):
    """Some provided resources were never used."""

    sort_key = (5, "unused")

    def __init__(self, resources):
        self.resources = resources

    def __str__(self):
        return 'Unused provided resources'

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

    sort_key = (6, "unsatisfied")

    def __init__(self, resources):
        self.resources = resources

    def __str__(self):
        return 'Unsatisfied resource requirements'

    def report(self):
        output.error("Unsatisfied resource requirements")
        for key in sorted(self.resources):
            output.line(
                '    Resource "{}" required by {}'.format(
                    key, ",".join(r.name for r in self.resources[key])),
                red=True)


class MissingEnvironment(ConfigurationError):
    """The specified environment does not exist."""

    sort_key = (0, )

    def __init__(self, environment):
        self.environment = environment

    def __str__(self):
        return 'Missing environment `{}`'.format(self.environment.name)

    def report(self):
        output.error("Missing environment")
        output.tabular("Environment", self.environment.name, red=True)


class MultipleEnvironmentConfigs(ConfigurationError):
    """The specified environment has multiple configurations.."""

    sort_key = (0, )

    def __init__(self, environment, configs):
        self.environment = environment
        self.configs

    def __str__(self):
        return 'Environment has multiple configs `{}`'.format(
            self.environment.name)

    def report(self):
        output.error("Multiple configs for environment")
        output.tabular("Environment", self.environment.name, red=True)
        for config in self.configs:
            output.tabular("Config", config, red=True)


class ComponentLoadingError(ConfigurationError):
    """The specified component file failed to load."""

    sort_key = (0, )

    def __init__(self, filename, exception):
        self.filename = filename
        self.exception = exception

    def __str__(self):
        return 'Failed loading component file ' + self.filename

    def report(self):
        output.error("Failed loading component file")
        output.tabular("File", self.filename, red=True)
        output.tabular("Exception", str(self.exception), red=True)
        # TODO provide traceback in debug output


class MissingComponent(ConfigurationError):
    """The specified environment does not exist."""

    sort_key = (0, )

    def __init__(self, component, hostname):
        self.component = component
        self.hostname = hostname

    def __str__(self):
        return 'Missing component: ' + self.component

    def report(self):
        output.error("Missing component")
        output.tabular("Component", self.component, red=True)
        output.tabular("Host", self.hostname, red=True)


class SuperfluousSection(ConfigurationError):
    """A superfluous section was found in the environment
    configuration file."""

    sort_key = (0, )

    def __init__(self, section):
        self.section = section

    def __str__(self):
        return 'Superfluous section in environment: ' + self.section

    def report(self):
        output.error("Superfluous section in environment configuration")
        output.tabular("Section", self.section, red=True)
        # TODO provide location and context in debug output


class SuperfluousComponentSection(ConfigurationError):
    """A component section was found in the environment
    but no associated component is known."""

    sort_key = (0, )

    def __init__(self, component):
        self.component = component

    def __str__(self):
        return ('Override section for unknown component found: ' +
                self.component)

    def report(self):
        output.error("Override section for unknown component found")
        output.tabular("Component", self.component, red=True)
        # TODO provide traceback in debug output


class SuperfluousSecretsSection(ConfigurationError):
    """A component section was found in the secrets
    but no associated component is known."""

    sort_key = (0, )

    def __init__(self, component):
        self.component = component

    def __str__(self):
        return 'Secrets section for unknown component found: ' + self.component

    def report(self):
        output.error("Secrets section for unknown component found")
        output.tabular("Component", self.component, red=True)
        # TODO provide traceback in debug output


class DuplicateOverride(ConfigurationError):
    """An override for a component attribute was found both in the secrets and
    in the environment configuration."""

    sort_key = (0, )

    def __init__(self, component, attribute):
        self.component = component
        self.attribute = attribute

    def __str__(self):
        return (f'A value {self.component}.{self.attribute} is defined both in'
                ' environment and secrets.')

    def report(self):
        output.error(
            "Attribute override found both in environment and secrets")
        output.tabular("Component", self.component, red=True)
        output.tabular("Attribute", self.attribute, red=True)
        # TODO provide traceback in debug output


class CycleErrorDetected(ConfigurationError):
    """We think we found a cycle in the component dependencies.
    """

    sort_key = (99, )

    def __init__(self, error):
        self.error = error

    def __str__(self):
        return 'Found dependency cycle.'

    def report(self):
        output.error("Found dependency cycle")
        output.annotate(str(self.error), red=True)
        # TODO provide traceback in debug output


class NonConvergingWorkingSet(ConfigurationError):
    """A working set did not converge."""

    sort_key = (100, )

    def __init__(self, roots):
        self.roots = roots

    def __str__(self):
        return 'There are unconfigured components remaining.'

    def report(self):
        # TODO show this last or first, but not in the middle
        # of everything
        output.error("{} remaining unconfigured component(s)".format(
            len(self.roots)))
        # TODO show all incl. their host name in -vv or so
        # output.annotate(', '.join(c.name for c in self.roots))


class DeploymentError(ReportingException):
    """Indicates that a deployment failed.."""

    sort_key = (100, )

    def __str__(self):
        return 'The deployment encountered an error.'

    def report(self):
        pass


class RepositoryDifferentError(DeploymentError):
    """The repository on the remote side is different."""

    sort_key = (150, )

    def __init__(self, local, remote):
        self.local = local
        self.remote = remote

    def __str__(self):
        return 'Remote repository has diverged. Wrong branch?'

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

    def __str__(self):
        return 'Duplicate host: ' + self.hostname

    def report(self):
        output.error("Duplicate definition of host: {}".format(self.hostname))


class InvalidIPAddressError(ConfigurationError):

    sort_key = (0, )

    def __init__(self, address):
        self.address = address

    def __str__(self):
        return 'Not a valid IP address: ' + self.address

    def report(self):
        output.error("Not a valid IP address: {}".format(self.address))


class IPAddressConfigurationError(ConfigurationError):
    """An IP address family was accessed but not configured."""

    sort_key = (0, )

    def __init__(self, address, kind: int):
        self.address = address
        self.kind = kind

    def __str__(self):
        return (f'Trying to access address family IPv{self.kind} which is not'
                f' configured for {self.address}.')

    def report(self):
        output.error(str(self))

        output.tabular(
            'Hint',
            f'Use `require_v{self.kind}=True` when instantiating the Address'
            ' object.')
