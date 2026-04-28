import contextlib
import subprocess
import types
from collections import UserString
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, Literal, Self, overload
from weakref import WeakKeyDictionary

import jinja2

from batou.environment import Environment
from batou.host import Host
from batou.utils import Timer

# Sentinel object for no default
NO_DEFAULT: object

class ConfigString(UserString): ...

class ComponentDefinition:
    filename: str
    name: str
    factory: Callable[[], Component]
    defdir: str

    def __init__(
        self,
        factory: Callable[[], Component],
        filename: str | None = ...,
        defdir: str | None = ...,
    ) -> None: ...

class Attribute[T]:
    conversion: type[T] | str | Callable[..., T]
    default: T | ConfigString | None
    expand: bool
    map: bool
    instances: WeakKeyDictionary[Component, T]
    names: dict[type, str]

    @overload
    def __get__(self, obj: None, objtype: type | None = ...) -> Self: ...
    @overload
    def __get__(
        self,
        obj: Any,  # Any: descriptor protocol allows any owner
        objtype: type | None = ...,
    ) -> T: ...
    @overload
    def __init__(
        self,
        conversion: type[T] | str | Callable[..., T],
        default: T | ConfigString | None = ...,
        expand: bool = ...,
        map: bool = ...,
    ) -> None: ...
    @overload
    def __init__(
        self,
        *,
        default: str | ConfigString | None = ...,
        expand: bool = ...,
        map: bool = ...,
    ) -> None: ...
    def __set__(self, obj: Any, value: T) -> None: ...  # Any: descriptor protocol
    def __set_name__(self, owner: type, name: str) -> None: ...
    def convert_list(self, value: str) -> list[str]: ...
    def convert_literal(
        self,
        value: str,
    ) -> Any: ...  # Any: depends on conversion target
    def from_config_string(
        self,
        obj: Any,  # Any: descriptor protocol
        value: ConfigString,
    ) -> Any: ...  # Any: return depends on conversion target

class Component:
    namevar: str | None
    workdir: str | None
    _: Component | None
    changed: bool
    _prepared: bool
    parent: Component | RootComponent
    sub_components: list[Component]
    timer: Timer
    _instances: list[Component]
    _template_engine: jinja2.Environment | None
    _platform_component: Component | None
    _event_handlers: dict[str, list[Callable[[Component], None]]]
    _init_file_path: str
    _init_line_number: int
    _init_breadcrumbs: list[str]

    def __repr__(self) -> str: ...  # noqa: PYI029, Y029
    def __add__(self, component: Component | None) -> Self: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        tb: types.TracebackType | None,
    ) -> bool | None: ...
    def __init__(
        self,
        namevar: str | Path | None = ...,
        **kw: Any,  # Any: arbitrary component kwargs
    ) -> None: ...
    def __or__(self, component: Component | None) -> Self: ...
    def __setup_event_handlers__(self) -> None: ...
    def __trigger_event__(self, event: str, predict_only: bool) -> None: ...
    @classmethod
    def _add_platform(cls, name: str, platform: type[Component]) -> None: ...
    @property
    def _breadcrumb(self) -> str: ...
    @property
    def _breadcrumbs(self) -> str: ...
    def _get_platform(self) -> Component | None: ...
    def _overrides(
        self,
        overrides: dict[str, Any] = ...,  # Any: override values heterogeneous
    ) -> None: ...
    def _template_args(
        self,
        component: Component | None = ...,
        **kw: Any,  # Any: template arguments heterogeneous
    ) -> dict[str, Any]: ...  # Any: template arguments heterogeneous
    def assert_cmd(
        self,
        *args: str,
        **kw: object,
    ) -> None: ...
    def assert_component_is_current(
        self,
        requirements: Component | list[Component] = ...,
        **kw: object,
    ) -> None: ...
    def assert_file_is_current(
        self,
        reference: str,
        requirements: list[str] = ...,
        **kw: object,
    ) -> None: ...
    def assert_no_changes(self) -> None: ...
    def assert_no_subcomponent_changes(self) -> None: ...
    def chdir(self, path: str) -> contextlib.AbstractContextManager[None]: ...
    def checksum(self, value: bytes | None = ...) -> str: ...
    @overload
    def cmd(
        self,
        cmd: str,
        silent: bool = ...,
        ignore_returncode: bool = ...,
        communicate: Literal[True] = ...,
        env: dict[str, str] | None = ...,
        expand: bool = ...,
    ) -> tuple[str, str]: ...
    @overload
    def cmd(
        self,
        cmd: str,
        silent: bool = ...,
        ignore_returncode: bool = ...,
        communicate: Literal[False] = ...,
        env: dict[str, str] | None = ...,
        expand: bool = ...,
    ) -> subprocess.Popen[str]: ...
    def configure(self) -> None: ...
    @property
    def defdir(self) -> str: ...
    def deploy(self, predict_only: bool = ...) -> None: ...
    @property
    def environment(self) -> Environment: ...
    def expand(
        self,
        string: str | ConfigString,
        component: Component | None = ...,
        **kw: Any,  # Any: template variables heterogeneous
    ) -> str: ...
    @property
    def host(self) -> Host: ...
    def last_updated(self) -> float | None: ...
    def log(self, message: str, *args: object) -> None: ...
    def map(self, path: Path | str) -> str: ...
    @property
    def namevar_for_breadcrumb(self) -> str | None: ...
    def prepare(self, parent: Component | RootComponent) -> None: ...
    def provide(self, key: str, value: object) -> None: ...
    @property
    def recursive_sub_components(self) -> Iterator[Component]: ...
    def require(
        self,
        key: str,
        host: Host | None = ...,
        strict: bool = ...,
        reverse: bool = ...,
        dirty: bool = ...,
    ) -> list[object]: ...
    def require_one(
        self,
        key: str,
        host: Host | None = ...,
        strict: bool = ...,
        reverse: bool = ...,
        dirty: bool = ...,
    ) -> object: ...
    @property
    def root(self) -> RootComponent: ...
    def template(self, filename: str, component: Component | None = ...) -> str: ...
    def touch(self, filename: str) -> None: ...
    def update(self) -> None: ...
    def verify(self) -> None: ...

class HookComponent(Component):
    key: str

    def configure(self) -> None: ...

class RootComponent:
    name: str
    environment: Environment
    host: Host
    features: Sequence[str] | None
    ignore: bool
    defdir: str
    workdir: str
    overrides: dict[str, Any]  # Any: override values heterogeneous
    factory: Callable[[], Component]
    component: Component
    _logs: list[tuple[str, tuple[str, ...]]] | None

    def __repr__(self) -> str: ...  # noqa: PYI029, Y029
    def __init__(
        self,
        name: str,
        environment: Environment,
        host: Host,
        features: Sequence[str] | None,
        ignore: bool,
        factory: Callable[[], Component],
        defdir: str,
        workdir: str,
        overrides: dict[str, Any] | None = ...,  # Any: override values heterogeneous
    ) -> None: ...
    @property
    def _breadcrumbs(self) -> str: ...
    def log(
        self,
        msg: str,
        *args: object,
    ) -> None: ...
    def log_finish_configure(self) -> None: ...
    def prepare(self) -> None: ...

def platform(name: str, component: type[Component]) -> Callable[[type[Component]], type[Component]]: ...
def handle_event(event: str, scope: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...
def check_event_scope(
    scope: Literal["*", "precursor"],
    source: Component,
    target: Component,
) -> bool: ...
def load_components_from_file(filename: str) -> dict[str, ComponentDefinition]: ...
def batou_generated_header(component: Component) -> str: ...
