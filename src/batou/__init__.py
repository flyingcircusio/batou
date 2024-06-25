# This code must not cause non-stdlib imports to support self-bootstrapping.
import os
import os.path
import socket
import traceback
from typing import List, Optional

import jinja2

from ._output import output

with open(os.path.dirname(__file__) + "/version.txt") as f:
    __version__ = f.read().strip()

# Configure `remote-pdb` to be used with `breakpoint()` in Python 3.7+:
os.environ["PYTHONBREAKPOINT"] = "remote_pdb.set_trace"
if not os.environ.get("REMOTE_PDB_HOST", None):
    os.environ["REMOTE_PDB_HOST"] = "127.0.0.1"
if not os.environ.get("REMOTE_PDB_PORT", None):
    os.environ["REMOTE_PDB_PORT"] = "4444"


def prepare_error(error):
    return f"{error.__class__.__name__}: {error}"


def prepare_traceback(tb):
    from batou import component, environment

    stack = traceback.extract_tb(tb)
    while stack:
        # Delete remoting-internal stack frames.'
        line = stack.pop(0)
        if line[0] in [
            "<string>",
            "<remote exec>",
            environment.__file__.rstrip("c"),
            component.__file__.rstrip("c"),
        ]:
            continue
        stack.insert(0, line)
        break
    if not stack:
        return "<no-non-remote-internal-traceback-lines-found>"
    return "".join(traceback.format_list(stack))


class ReportingException(Exception):
    """Exceptions that support user-readable reporting."""

    affected_hostname: Optional[str]

    def __str__(self):
        raise NotImplementedError()

    def report(self):
        raise NotImplementedError()

    def should_merge(self, other):
        """
        checks, wether two exceptions have the same type as well as data
        and as such, should be merged into one exception.
        """
        # generic check:
        # the other class should have: the same class as self, in both directions
        if type(other) != type(self):
            return False
        # now both should have the same attributes
        # compare by all attributes except: .affected_hostname
        dict_self = self.__dict__.copy()
        dict_self.pop("affected_hostname", None)
        dict_other = other.__dict__.copy()
        dict_other.pop("affected_hostname", None)
        return dict_self == dict_other

    @classmethod
    def merge(cls, selfs):
        """Merge multiple instances of this exception."""
        # remove and collect .affected_hostname from all exceptions
        if hasattr(selfs[0], "affected_hostname"):
            hostnames = set()
            for self in selfs:
                hostnames.add(self.affected_hostname)
        else:
            hostnames = None
        # create a new exception with the merged attributes
        first_self_dict = selfs[0].__dict__.copy()
        first_self_dict.pop("affected_hostname", None)
        new_exception = cls()
        new_exception.__dict__.update(first_self_dict)
        new_exception.affected_hostname = "<HOSTNAME>"
        return (new_exception, hostnames)


class FileLockedError(ReportingException):
    """A file is already locked and we do not want to block."""

    filename: str

    @classmethod
    def from_context(cls, filename):
        self = cls()
        self.filename = filename
        return self

    def __str__(self):
        return "File already locked: {}".format(self.filename)

    def report(self):
        output.error(str(self))


class GPGCallError(ReportingException):
    """There was an error calling GPG on encrypted file."""

    command: str
    exitcode: str
    output: str

    @classmethod
    def from_context(cls, command, exitcode, output):
        self = cls()
        self.command = " ".join(command)
        self.exitcode = str(exitcode)
        self.output = output.decode("ascii", errors="replace")
        return self

    def __str__(self):
        return (
            f"Exitcode {self.exitcode} while calling: "
            f"{self.command}\n{self.output}"
        )

    def report(self):
        output.error("Error while calling GPG")
        output.tabular("command", self.command, red=True)
        output.tabular("exit code", self.exitcode)
        output.tabular("message", self.output, separator=":\n")


class AgeCallError(ReportingException):
    """There was an error calling age on encrypted file."""

    command: str
    exitcode: str
    output: str

    @classmethod
    def from_context(cls, command, exitcode, output):
        self = cls()
        self.command = " ".join(command)
        self.exitcode = str(exitcode)
        self.output = output.decode("ascii", errors="replace")
        return self

    def __str__(self):
        return (
            f"Exitcode {self.exitcode} while calling: "
            f"{self.command}\n{self.output}"
        )

    def report(self):
        output.error("Error while calling age")
        output.tabular("command", self.command, red=True)
        output.tabular("exit code", self.exitcode)
        output.tabular("message", self.output, separator=":\n")


class GetAddressInfoError(ReportingException, socket.gaierror):
    """There was an error calling getaddrinfo."""

    hostname: str
    error: str

    @classmethod
    def from_context(cls, hostname, error):
        self = cls()
        self.hostname = hostname
        self.error = error
        return self

    def __str__(self):
        return f"Error while resolving {self.hostname}: {self.error}"

    def report(self):
        output.error("Error while resolving hostname")
        output.tabular("hostname", self.hostname, red=True)
        output.tabular("message", self.error, separator=":\n")


class UpdateNeeded(AssertionError):
    """A component requires an update."""


class ConfigurationError(ReportingException):
    """Indicates that an environment could not be configured successfully."""

    message: str
    has_component: bool
    component_root_name: Optional[str]

    @property
    def sort_key(self):
        return (0, self.message)

    @classmethod
    def from_context(cls, message, component=None):
        self = cls()
        self.message = message
        self.has_component = component is not None
        self.component_root_name = component.root.name if component else None
        self.affected_hostname = component.root.host.name if component else None
        return self

    def __str__(self):
        return str(self.message)

    def report(self):
        message = self.message
        if self.has_component:
            message = "{}: {}".format(
                self.component_root_name,
                message,
            )
        output.error(message)


class AttributeExpansionError(ConfigurationError):
    """An override attribute could not be expanded properly."""

    component_breadcrumbs: str
    value_repr: str
    error_str: str
    key: str

    @property
    def sort_key(self):
        return (
            1,
            self.affected_hostname,
            self.component_breadcrumbs,
            self.key,
        )

    @classmethod
    def from_context(cls, component, key, value, error):
        self = cls()
        self.affected_hostname = component.root.host.name
        self.component_breadcrumbs = component._breadcrumbs
        self.value_repr = repr(value)
        self.error = prepare_error(error)
        self.key = key
        return self

    def __str__(self):
        return "Error while expanding attribute: " + self.error

    def report(self):
        output.error("Error while expanding attribute:")
        output.tabular(
            "Message",
            self.error,
            red=True,
        )
        output.tabular(
            "Attribute",
            "{}.{}".format(self.component_breadcrumbs, self.key),
            red=True,
        )


class ConversionError(ConfigurationError):
    """An override attribute could not be converted properly."""

    component_breadcrumbs: str
    conversion_name: str
    value_repr: str
    error_str: str
    key: str

    @property
    def sort_key(self):
        return (
            1,
            self.affected_hostname,
            self.component_breadcrumbs,
            self.key,
        )

    @classmethod
    def from_context(cls, component, key, value, conversion, error):
        self = cls()
        self.affected_hostname = component.root.host.name
        self.component_breadcrumbs = component._breadcrumbs
        self.conversion_name = conversion.__name__
        self.value_repr = repr(value)
        self.error_str = str(error)
        self.key = key
        return self

    def __str__(self):
        return self.error_str

    def report(self):
        output.error(self.error_str)
        output.tabular(
            "Attribute",
            "{}.{}".format(self.component_breadcrumbs, self.key),
            red=True,
        )
        output.tabular(
            "Conversion",
            "{}({})".format(self.conversion_name, self.value_repr),
            red=True,
        )
        # TODO provide traceback in debug output
        # provide file, line number, excerpt of attribute definition
        # see: https://github.com/flyingcircusio/batou/issues/316


class SilentConfigurationError(Exception):
    """These are exceptions that will be reported by other exceptions.

    They basically only influence control flow during configuration and
    are manually placed to avoid double reporting.

    """


class MissingOverrideAttributes(ConfigurationError):
    component_breadcrumbs: str
    attributes: List[str]

    @property
    def sort_key(self):
        return (3, self.affected_hostname, self.component_breadcrumbs)

    @classmethod
    def from_context(cls, component, attributes):
        self = cls()
        self.affected_hostname = component.root.host.name
        self.component_breadcrumbs = component._breadcrumbs
        self.attributes = attributes
        return self

    def __str__(self):
        return "Overrides for undefined attributes " + ",".join(self.attributes)

    def report(self):
        output.error("Overrides for undefined attributes")
        output.tabular("Component", self.component_breadcrumbs, red=True)
        output.tabular("Attributes", ", ".join(self.attributes), red=True)

        # TODO point to specific line in secrets or environments
        # cfg file and show context


class DuplicateComponent(ConfigurationError):
    a_name: str
    a_filename: str
    b_filename: str

    @property
    def sort_key(self):
        return (2, self.a_name)

    @classmethod
    def from_context(cls, a, b):
        self = cls()
        self.a_name = a.name
        self.a_filename = a.filename
        self.b_filename = b.filename
        return self

    def __str__(self):
        return "Duplicate component: " + self.a_name

    def report(self):
        output.error('Duplicate component "{}"'.format(self.a_name))
        output.tabular("Occurrence", self.a_filename)
        output.tabular("Occurrence", self.b_filename)


class DuplicateHostMapping(ConfigurationError):
    affected_hostname: str
    a: str
    b: str

    @property
    def sort_key(self):
        return (3, self.affected_hostname, self.a, self.b)

    @classmethod
    def from_context(cls, hostname, a, b):
        self = cls()
        self.affected_hostname = hostname
        self.a = a
        self.b = b
        return self

    def __str__(self):
        return "Duplicate host mapping: " + self.affected_hostname

    def report(self):
        output.error(
            'Duplicate host mapping "{}"'.format(self.affected_hostname)
        )
        output.tabular("Mapping 1: ", self.a)
        output.tabular("Mapping 2: ", self.b)


class UnknownComponentConfigurationError(ConfigurationError):
    """An unknown error occured while configuring a component."""

    @property
    def sort_key(self):
        return (4, self.root_host_name, 2)

    @classmethod
    def from_context(cls, root, exception, tb):
        self = cls()
        self.root_name = root.name
        self.root_host_name = root.host.name
        self.exception_repr = prepare_error(exception)
        stack = traceback.extract_tb(tb)
        from batou import component, environment

        self.traceback = prepare_traceback(tb)
        return self

    def __str__(self):
        return self.exception_repr

    def report(self):
        output.error(self.exception_repr)
        output.annotate(
            "This /might/ be a batou bug. Please consider reporting it.\n",
            red=True,
        )
        output.tabular("Host", self.root_host_name, red=True)
        output.tabular("Component", self.root_name + "\n", red=True)
        output.annotate(
            "Traceback (simplified, most recent call last):", red=True
        )
        output.annotate(self.traceback, red=True)


class UnusedResources(ConfigurationError):
    """Some provided resources were never used."""

    sort_key = (5, "unused")

    @classmethod
    def from_context(cls, resources):
        self = cls()
        self.unused_resources = []
        for key in sorted(resources.keys()):
            for component, value in resources[key].items():
                self.unused_resources.append((key, component.name, str(value)))
        return self

    def __str__(self):
        return "Unused provided resources"

    def report(self):
        output.error("Unused provided resources")
        for key, component, value in self.unused_resources:
            output.line(
                '    Resource "{}" provided by {} with value {}'.format(
                    key, component, value
                ),
                red=True,
            )


class UnusedComponentsInitialized(ConfigurationError):
    """Some components were initialized but never used."""

    sort_key = (5, "unused")

    @classmethod
    def from_context(cls, components, root):
        self = cls()
        self.unused_components = []
        self.breadcrumbs = []
        self.init_file_paths = []
        self.init_line_numbers = []
        for component in components:
            self.unused_components.append(repr(component.__class__.__name__))
            self.breadcrumbs.append(component._init_breadcrumbs)
            self.init_file_paths.append(component._init_file_path)
            self.init_line_numbers.append(component._init_line_number)
        self.root_name = root.name
        return self

    def __str__(self):
        out_str = "Some components were initialized but never added to the environment:"
        for i, component in enumerate(self.unused_components):
            out_str += f"\n    {component}: {' -> '.join(self.breadcrumbs[i])}"
            out_str += f"\n        initialized in {self.init_file_paths[i]}:{self.init_line_numbers[i]}"
        out_str += f"\nRoot: {self.root_name}"
        out_str += f"\nAdd the components to the environment using `self += component`."
        return out_str

    def report(self):
        output.error(
            f"Some components were initialized but never added to the environment:"
        )
        for i, component in enumerate(self.unused_components):
            output.line(
                f"    {component}: {' -> '.join(self.breadcrumbs[i])}", red=True
            )
            output.line(
                f"        initialized in {self.init_file_paths[i]}:{self.init_line_numbers[i]}",
                red=True,
            )
        output.line(
            f"Add the components to the environment using `self += component`.",
            red=True,
        )
        output.tabular("Root", self.root_name, red=True)


class UnsatisfiedResources(ConfigurationError):
    """Some required resources were never provided."""

    sort_key = (6, "unsatisfied")

    @classmethod
    def from_context(cls, resources):
        self = cls()
        self.unsatisfied_resources = []
        for key in sorted(resources.keys()):
            self.unsatisfied_resources.append(
                (key, [r.name for r in resources[key]])
            )
        return self

    def __str__(self):
        return "Unsatisfied resource requirements"

    def report(self):
        output.error("Unsatisfied resource requirements")
        for key, resources in self.unsatisfied_resources:
            output.line(
                '    Resource "{}" required by {}'.format(
                    key, ",".join(resources)
                ),
                red=True,
            )


class MissingEnvironment(ConfigurationError):
    """The specified environment does not exist."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, environment):
        self = cls()
        self.environment_name = environment.name
        return self

    def __str__(self):
        return "Missing environment `{}`".format(self.environment_name)

    def report(self):
        output.error("Missing environment")
        output.tabular("Environment", self.environment_name, red=True)


class ComponentLoadingError(ConfigurationError):
    """The specified component file failed to load."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, filename, exception, tb):
        self = cls()
        self.filename = filename
        self.exception_str = str(exception)

        self.traceback = prepare_traceback(tb)
        return self

    def __str__(self):
        return "Failed loading component file " + self.filename

    def report(self):
        output.error("Failed loading component file")
        output.tabular("File", self.filename, red=True)
        output.tabular("Exception", self.exception_str, red=True)
        output.annotate(
            "Traceback (simplified, most recent call last):", red=True
        )
        output.annotate(self.traceback, red=True)

        # TODO provide traceback in debug output
        # see: https://github.com/flyingcircusio/batou/issues/316


class MissingComponent(ConfigurationError):
    """The specified environment does not exist."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, component_name, hostname):
        self = cls()
        self.component_name = component_name
        self.affected_hostname = hostname
        return self

    def __str__(self):
        return "Missing component: " + self.component_name

    def report(self):
        output.error("Missing component")
        output.tabular("Component", self.component_name, red=True)


class SuperfluousSection(ConfigurationError):
    """A superfluous section was found in the environment
    configuration file."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, section):
        self = cls()
        self.section = section
        return self

    def __str__(self):
        return "Superfluous section in environment: " + self.section

    def report(self):
        output.error("Superfluous section in environment configuration")
        output.tabular("Section", self.section, red=True)
        # TODO provide location and context in debug output
        # see: https://github.com/flyingcircusio/batou/issues/316


class SuperfluousComponentSection(ConfigurationError):
    """A component section was found in the environment
    but no associated component is known."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, component_name):
        self = cls()
        self.component_name = component_name
        return self

    def __str__(self):
        return (
            "Override section for unknown component found: "
            + self.component_name
        )

    def report(self):
        output.error("Override section for unknown component found")
        output.tabular("Component", self.component_name, red=True)
        # TODO provide traceback in debug output
        # see: https://github.com/flyingcircusio/batou/issues/316


class SuperfluousSecretsSection(ConfigurationError):
    """A component section was found in the secrets
    but no associated component is known."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, component_name):
        self = cls()
        self.component_name = component_name
        return self

    def __str__(self):
        return (
            "Secrets section for unknown component found: "
            + self.component_name
        )

    def report(self):
        output.error("Secrets section for unknown component found")
        output.tabular("Component", self.component_name, red=True)
        # TODO provide traceback in debug output
        # see: https://github.com/flyingcircusio/batou/issues/316


class UnknownHostSecretsSection(ConfigurationError):
    """A host section was found in the secrets
    but no associated host is known."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, hostname):
        self = cls()
        self.hostname = hostname
        return self

    def __str__(self):
        return "Secrets section for unknown host found: " + self.hostname

    def report(self):
        output.error("Secrets section for unknown host found")
        output.tabular("Host", self.hostname, red=True)


class DuplicateOverride(ConfigurationError):
    """An override for a component attribute was found both in the secrets and
    in the environment configuration."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, component_name, attribute):
        self = cls()
        self.component_name = component_name
        self.attribute = attribute
        return self

    def __str__(self):
        return (
            f"A value {self.component_name}.{self.attribute} is defined both in"
            " environment and secrets."
        )

    def report(self):
        output.error("Attribute override found both in environment and secrets")
        output.tabular("Component", self.component_name, red=True)
        output.tabular("Attribute", self.attribute, red=True)
        # TODO provide traceback in debug output
        # see: https://github.com/flyingcircusio/batou/issues/316


class DuplicateSecretsComponentAttribute(ConfigurationError):
    """A component attribute was specified multiple times in the secrets."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, component_name, attribute):
        self = cls()
        self.component_name = component_name
        self.attribute = attribute
        return self

    def __str__(self):
        return (
            f"A value {self.component_name}.{self.attribute} is defined multiple"
            " times in secrets."
        )

    def report(self):
        output.error("Attribute defined multiple times in secrets")
        output.tabular("Component", self.component_name, red=True)
        output.tabular("Attribute", self.attribute, red=True)
        # TODO provide traceback in debug output
        # see: https://github.com/flyingcircusio/batou/issues/316


class CycleErrorDetected(ConfigurationError):
    """We think we found a cycle in the component dependencies."""

    sort_key = (99,)

    @classmethod
    def from_context(cls, error):
        self = cls()
        self.error_str = str(error)
        return self

    def report(self):
        output.error("Found dependency cycle")
        output.annotate(self.error_str, red=True)
        # TODO provide traceback in debug output
        # see: https://github.com/flyingcircusio/batou/issues/316

    def __str__(self):
        return "Found dependency cycle: " + self.error_str


class NonConvergingWorkingSet(ConfigurationError):
    """A working set did not converge."""

    sort_key = (100,)

    @classmethod
    def from_context(cls, roots):
        self = cls()
        self.roots_len = len(roots)
        self.root_names = ", ".join(sorted([r.name for r in roots]))
        return self

    def __str__(self):
        return "There are unconfigured components remaining."

    def report(self):
        # TODO show this last or first, but not in the middle
        # of everything
        output.error(
            "{} remaining unconfigured component(s): {}".format(
                self.roots_len, self.root_names
            )
        )
        # TODO show all incl. their host name in -vv or so


class DeploymentError(ReportingException):
    """Indicates that a deployment failed.."""

    sort_key = (100,)

    def __str__(self):
        return "The deployment encountered an error."

    def report(self):
        pass


class RepositoryDifferentError(DeploymentError):
    """The repository on the remote side is different."""

    sort_key = (150,)

    @classmethod
    def from_context(cls, local, remote):
        self = cls()
        self.local = local
        self.remote = remote
        return self

    def __str__(self):
        return "Remote repository has diverged. Wrong branch?"

    def report(self):
        output.error(
            "The remote working copy is based on a different revision. "
            "Maybe you tried to deploy from the wrong branch."
        )
        output.tabular("Local", self.local, red=True)
        output.tabular("Remote", self.remote, red=True)


class DuplicateHostError(ConfigurationError):
    @property
    def sort_key(self):
        return (0,)

    @classmethod
    def from_context(cls, hostname):
        self = cls()
        self.affected_hostname = hostname
        return self

    def __str__(self):
        return "Duplicate host: " + self.affected_hostname

    def report(self):
        output.error(
            "Duplicate definition of host: {}".format(self.affected_hostname)
        )


class InvalidIPAddressError(ConfigurationError):
    sort_key = (0,)

    @classmethod
    def from_context(cls, address):
        self = cls()
        self.address = address
        return self

    def __str__(self):
        return "Not a valid IP address: " + self.address

    def report(self):
        output.error("Not a valid IP address: {}".format(self.address))


class IPAddressConfigurationError(ConfigurationError):
    """An IP address family was accessed but not configured."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, address, kind):
        self = cls()
        self.address = address
        self.kind = kind
        return self

    def __str__(self):
        return (
            f"Trying to access address family IPv{self.kind} which is not"
            f" configured for {self.address}."
        )

    def report(self):
        output.error(str(self))

        output.tabular(
            "Hint",
            f"Use `require_v{self.kind}=True` when instantiating the Address"
            " object.",
            red=True,
        )

        # TODO provide traceback/line numbers/excerpt
        # see: https://github.com/flyingcircusio/batou/issues/316


class TemplatingError(ReportingException):
    """An error occured while rendering a template."""

    sort_key = (0,)

    @classmethod
    def from_context(cls, exception, template_identifier):
        self = cls()
        self.exception_str = prepare_error(exception)
        self.template_identifier = template_identifier
        # if exception is instance of jinja2.TemplateSyntaxError
        # there is some magic in jinja2 that makes the __str__ method
        # less capable, if exception.translated is set to True
        if isinstance(exception, jinja2.TemplateSyntaxError):
            exception.translated = False
            self.exception_str = str(exception)
            exception.translated = True
        return self

    def __str__(self):
        return f"An error occured while rendering a template ({self.template_identifier}): {self.exception_str}"

    def report(self):
        output.error(str(self))
