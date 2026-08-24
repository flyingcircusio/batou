import socket
from collections.abc import Callable, Sequence
from traceback import StackSummary
from types import TracebackType
from typing import Any

from batou.component import Component, ComponentDefinition, RootComponent
from batou.environment import Environment

__version__: str
output: Any  # circular import with _output module

def prepare_error(error: Exception) -> str: ...
def prepare_traceback(tb: TracebackType) -> str: ...
def prepare_traceback_from_stack(stack: StackSummary) -> str: ...

class ReportingException(Exception):
    affected_hostname: str | None

    def __str__(self) -> str: ...  # noqa: PYI029, Y029
    def report(self) -> None: ...
    def should_merge(self, other: ReportingException) -> bool: ...
    @classmethod
    def merge(cls, selfs: list[ReportingException]) -> tuple[ReportingException, set[str] | None]: ...

class AgeCallError(ReportingException):
    command: str
    exitcode: str
    output: str

    @classmethod
    def from_context(cls, command: list[str], exitcode: int, output: bytes) -> AgeCallError: ...  # type: ignore[override]
    def report(self) -> None: ...

class AttributeExpansionError(ConfigurationError):
    component_breadcrumbs: str
    value_repr: str
    error: str
    error_str: str
    key: str

    @classmethod
    def from_context(  # type: ignore[override]
        cls, component: Component, key: str, value: object, error: Exception
    ) -> AttributeExpansionError: ...
    @property
    def sort_key(self) -> tuple[int, str, str, str]: ...

class ComponentLoadingError(ReportingException):
    filename: str
    exception_str: str
    traceback: str
    exception: Exception

    @classmethod
    def from_context(  # type: ignore[override]
        cls, filename: str, exception: Exception, tb: TracebackType
    ) -> ComponentLoadingError: ...
    @property
    def sort_key(self) -> tuple[int | str, ...]: ...
    def report(self) -> None: ...

class ComponentUsageError(ConfigurationError):
    message: str
    traceback: str

    @classmethod
    def from_context(cls, message: str) -> ComponentUsageError: ...  # type: ignore[override]
    @property
    def sort_key(self) -> tuple[int, str]: ...

class ComponentWithUpdateWithoutVerify(ConfigurationError):
    components: list[str]
    roots: list[str]

    @property
    def sort_key(self) -> tuple[int, str]: ...
    @classmethod
    def from_context(  # type: ignore[override]
        cls, components: list[Component], roots: list[Component]
    ) -> ComponentWithUpdateWithoutVerify: ...

class ConfigurationError(ReportingException):
    message: str
    has_component: bool
    component_root_name: str | None

    @classmethod
    def from_context(cls, message: str, component: Component | None = ...) -> ConfigurationError: ...  # type: ignore[override]
    def report(self) -> None: ...
    @property
    def sort_key(self) -> tuple[Any, ...]: ...

class ConversionError(ConfigurationError):
    component_breadcrumbs: str
    conversion_name: str
    value_repr: str
    error_str: str
    key: str

    @classmethod
    def from_context(  # type: ignore[override]
        cls, component: Component, key: str, value: object, conversion: type | str | Callable[..., object], error: Exception
    ) -> ConversionError: ...
    @property
    def sort_key(self) -> tuple[int, str, str, str, str]: ...

class CycleErrorDetected(ConfigurationError):
    error_str: str

    @property
    def sort_key(self) -> tuple[int, ...]: ...
    @classmethod
    def from_context(cls, error: object) -> CycleErrorDetected: ...  # type: ignore[override]

class DeploymentError(ReportingException):
    @property
    def sort_key(self) -> tuple[int, ...]: ...
    def report(self) -> None: ...

class DuplicateComponent(ConfigurationError):
    a_name: str
    a_filename: str
    b_filename: str

    @classmethod
    def from_context(cls, a: ComponentDefinition, b: ComponentDefinition) -> DuplicateComponent: ...  # type: ignore[override]
    @property
    def sort_key(self) -> tuple[int, str]: ...

class DuplicateHostError(ConfigurationError):
    @classmethod
    def from_context(cls, hostname: str) -> DuplicateHostError: ...  # type: ignore[override]
    @property
    def sort_key(self) -> tuple[int, str]: ...

class DuplicateHostMapping(ConfigurationError):
    a: str
    b: str

    @classmethod
    def from_context(cls, hostname: str, a: str, b: str) -> DuplicateHostMapping: ...  # type: ignore[override]
    @property
    def sort_key(self) -> tuple[int, str, str, str]: ...

class DuplicateOverride(ConfigurationError):
    component_name: str
    attribute: str

    @classmethod
    def from_context(cls, component_name: str, attribute: str) -> DuplicateOverride: ...  # type: ignore[override]

class DuplicateSecretsComponentAttribute(ConfigurationError):
    component_name: str
    attribute: str

    @classmethod
    def from_context(  # type: ignore[override]
        cls, component_name: str, attribute: str
    ) -> DuplicateSecretsComponentAttribute: ...

class FileLockedError(ReportingException):
    filename: str

    @classmethod
    def from_context(cls, filename: str) -> FileLockedError: ...
    def report(self) -> None: ...

class GetAddressInfoError(ReportingException, socket.gaierror):
    hostname: str
    error: str

    @classmethod
    def from_context(cls, hostname: str, error: str) -> GetAddressInfoError: ...

class GPGCallError(ReportingException):
    command: str
    exitcode: str
    output: str

    @classmethod
    def from_context(cls, command: list[str], exitcode: int, output: bytes) -> GPGCallError: ...  # type: ignore[override]
    def report(self) -> None: ...

class IPAddressConfigurationError(ConfigurationError):
    address: object
    kind: int

    @classmethod
    def from_context(cls, address: object, kind: int) -> IPAddressConfigurationError: ...  # type: ignore[override]

class InvalidIPAddressError(ConfigurationError):
    address: str

    @classmethod
    def from_context(cls, address: str) -> InvalidIPAddressError: ...  # type: ignore[override]

class MissingComponent(ConfigurationError):
    component_name: str

    @classmethod
    def from_context(cls, component_name: str, hostname: str) -> MissingComponent: ...  # type: ignore[override]

class MissingEnvironment(ConfigurationError):
    environment_name: str

    @classmethod
    def from_context(cls, environment: Environment) -> MissingEnvironment: ...  # type: ignore[override]

class MissingOverrideAttributes(ConfigurationError):
    component_breadcrumbs: str
    attributes: list[str]

    @classmethod
    def from_context(cls, component: Component, attributes: list[str]) -> MissingOverrideAttributes: ...  # type: ignore[override]
    @property
    def sort_key(self) -> tuple[int, str, str]: ...

class NonConvergingWorkingSet(ConfigurationError):
    roots_len: int
    root_names: str

    @property
    def sort_key(self) -> tuple[int | str, ...]: ...
    @classmethod
    def from_context(cls, roots: Sequence[RootComponent]) -> NonConvergingWorkingSet: ...  # type: ignore[override]

class RepositoryDifferentError(DeploymentError):
    local: str
    remote: str

    @classmethod
    def from_context(cls, local: str, remote: str) -> RepositoryDifferentError: ...

class SilentConfigurationError(Exception): ...

class SuperfluousComponentSection(ConfigurationError):
    component_name: str

    @classmethod
    def from_context(cls, component_name: str) -> SuperfluousComponentSection: ...  # type: ignore[override]

class SuperfluousSecretsSection(ConfigurationError):
    component_name: str

    @classmethod
    def from_context(cls, component_name: str) -> SuperfluousSecretsSection: ...  # type: ignore[override]

class SuperfluousSection(ConfigurationError):
    section: str

    @classmethod
    def from_context(cls, section: str) -> SuperfluousSection: ...  # type: ignore[override]

class TemplatingError(ReportingException):
    exception_str: str
    template_identifier: str

    @property
    def sort_key(self) -> tuple[int | str, ...]: ...
    @classmethod
    def from_context(cls, exception: Exception, template_identifier: str) -> TemplatingError: ...  # type: ignore[override]

class UnknownComponentConfigurationError(ConfigurationError):
    root_name: str
    root_host_name: str
    exception_repr: str
    traceback: str

    @classmethod
    def from_context(  # type: ignore[override]
        cls, root: RootComponent, exception: Exception, tb: TracebackType
    ) -> UnknownComponentConfigurationError: ...
    @property
    def sort_key(self) -> tuple[int, str, int]: ...

class UnknownHostSecretsSection(ConfigurationError):
    hostname: str

    @classmethod
    def from_context(cls, hostname: str) -> UnknownHostSecretsSection: ...  # type: ignore[override]

class UnsatisfiedResources(ConfigurationError):
    unsatisfied_resources: list[tuple[str, str | None, list[str]]]

    @classmethod
    def from_context(cls, resources: object) -> UnsatisfiedResources: ...  # type: ignore[override]

class UnusedComponentsInitialized(ConfigurationError):
    unused_components: list[str]
    breadcrumbs: list[list[str]]
    init_file_paths: list[str]
    init_line_numbers: list[int]
    root_name: str

    @property
    def sort_key(self) -> tuple[int, str]: ...
    @classmethod
    def from_context(  # type: ignore[override]
        cls, components: list[Component], root: RootComponent
    ) -> UnusedComponentsInitialized: ...

class UnusedResources(ConfigurationError):
    unused_resources: list[tuple[str, str, str]]

    @property
    def sort_key(self) -> tuple[int, str]: ...
    @classmethod
    def from_context(cls, resources: object) -> UnusedResources: ...  # type: ignore[override]

class UpdateNeeded(AssertionError): ...
