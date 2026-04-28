import os
import typing
from collections.abc import Callable, Iterator
from typing import Any, Literal

from batou.component import Attribute, Component, RootComponent

def convert_mode(string: str) -> int: ...
def ensure_path_nonexistent(path: str) -> None: ...
def limited_buffer(
    iterator: Iterator[str],
    limit: int,
    lead: int,
    separator: str = ...,
    logdir: str = ...,
) -> tuple[list[str], bool, str]: ...

class File(Component):
    namevar: str
    ensure: Literal["file", "directory", "symlink"]
    content: str | bytes | None
    source: str
    is_template: bool
    template_context: Component | RootComponent | None
    template_args: dict[str, Any] | None  # Any: template arguments of arbitrary types
    encoding: str | None
    owner: str | None
    group: str | None
    mode: str | int | None
    link_to: str
    leading: bool
    sensitive_data: bool | None
    path: str
    _unmapped_path: str

    def __init__(
        self,
        path: str | None = ...,
        *,
        ensure: Literal["file", "directory", "symlink"] = ...,
        content: str | bytes | None = ...,
        source: str = ...,
        is_template: bool = ...,
        template_context: Component | RootComponent | None = ...,
        template_args: dict[str, Any] | None = ...,
        encoding: str | None = ...,
        owner: str | None = ...,
        group: str | None = ...,
        mode: str | int | None = ...,
        link_to: str = ...,
        leading: bool = ...,
        sensitive_data: bool | None = ...,
    ) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @typing.override
    def last_updated(self, key: str = ...) -> float | None: ...
    @property
    @typing.override
    def namevar_for_breadcrumb(self) -> str: ...

class BinaryFile(File):
    is_template: bool
    encoding: None
    content: bytes | None  # type: ignore[assignment]
    source: str | None  # type: ignore[assignment]

class Presence(Component):
    namevar: str
    leading: bool
    path: str

    def __init__(
        self,
        path: str | None = ...,
        *,
        leading: bool = ...,
    ) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @typing.override
    def last_updated(self, key: str = ...) -> float | None: ...
    @property
    @typing.override
    def namevar_for_breadcrumb(self) -> str: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...

class SyncDirectory(Component):
    namevar: str
    source: str | None
    exclude: tuple[str, ...]
    verify_opts: str
    sync_opts: str
    path: str

    def __init__(
        self,
        path: str | None = ...,
        *,
        source: str | None = ...,
        exclude: tuple[str, ...] = ...,
        verify_opts: str = ...,
        sync_opts: str = ...,
    ) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @property
    def exclude_arg(self) -> str: ...
    @property
    @typing.override
    def namevar_for_breadcrumb(self) -> str: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...

class Directory(Component):
    namevar: str
    leading: bool
    source: str | None
    exclude: tuple[str, ...]
    verify_opts: str | None
    sync_opts: str | None
    path: str

    def __init__(
        self,
        path: str | None = ...,
        *,
        leading: bool = ...,
        source: str | None = ...,
        exclude: tuple[str, ...] = ...,
        verify_opts: str | None = ...,
        sync_opts: str | None = ...,
    ) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @typing.override
    def last_updated(self, key: str = ...) -> float: ...
    @property
    @typing.override
    def namevar_for_breadcrumb(self) -> str: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...

class FileComponent(Component):
    namevar: str
    leading: bool
    original_path: str
    path: str

    def __init__(
        self,
        path: str | None = ...,
        *,
        leading: bool = ...,
    ) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @property
    @typing.override
    def namevar_for_breadcrumb(self) -> str: ...

class ManagedContentBase(FileComponent):
    content: bytes | str | None
    source: str
    sensitive_data: bool | None
    encoding: str | None
    _delayed: bool
    _max_diff: int
    _max_diff_lead: int
    _content_source_attribute: str
    diff_dir: str

    def __init__(
        self,
        path: str | None = ...,
        *,
        content: bytes | str | None = ...,
        source: str = ...,
        sensitive_data: bool | None = ...,
        encoding: str | None = ...,
    ) -> None: ...
    def _render(self) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(
        self,
        predicting: bool = ...,
    ) -> None: ...

class Content(ManagedContentBase):
    is_template: bool
    template_context: Component | RootComponent | None
    template_args: dict[str, Any] | None  # Any: template arguments of arbitrary types

    def __init__(
        self,
        path: str | None = ...,
        *,
        content: bytes | str | None = ...,
        source: str = ...,
        sensitive_data: bool | None = ...,
        encoding: str | None = ...,
        is_template: bool = ...,
        template_context: Component | RootComponent | None = ...,
        template_args: dict[str, Any] | None = ...,
    ) -> None: ...
    def render(self) -> None: ...

class JSONContent(ManagedContentBase):
    data: Any  # Any: arbitrary JSON data
    override: dict[str, Any] | None  # Any: JSON override values
    human_readable: bool
    content_compact: str | None
    content_readable: str | None

    def __init__(
        self,
        path: str | None = ...,
        *,
        content: bytes | str | None = ...,
        source: str = ...,
        sensitive_data: bool | None = ...,
        encoding: str | None = ...,
        data: Any = ...,
        override: dict[str, Any] | None = ...,
        human_readable: bool = ...,
    ) -> None: ...
    def render(self) -> None: ...

class YAMLContent(ManagedContentBase):
    data: Any  # Any: arbitrary YAML data
    override: dict[str, Any] | None  # Any: YAML override values

    def __init__(
        self,
        path: str | None = ...,
        *,
        content: bytes | str | None = ...,
        source: str = ...,
        sensitive_data: bool | None = ...,
        encoding: str | None = ...,
        data: Any = ...,
        override: dict[str, Any] | None = ...,
    ) -> None: ...
    def render(self) -> None: ...

class Owner(FileComponent):
    owner: str | int | None

    def __init__(
        self,
        path: str | None = ...,
        *,
        leading: bool = ...,
        owner: str | int | None = ...,
    ) -> None: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...

class Group(FileComponent):
    group: str | int | None

    def __init__(
        self,
        path: str | None = ...,
        *,
        leading: bool = ...,
        group: str | int | None = ...,
    ) -> None: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...

class Mode(FileComponent):
    mode: Attribute[int | str | None]
    _stat: Callable[[str], os.stat_result]
    _chmod: Callable[[str, int], None]

    def __init__(
        self,
        path: str | None = ...,
        *,
        leading: bool = ...,
    ) -> None: ...
    def _select_stat_implementation(self) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...

class Symlink(Component):
    namevar: str
    source: str | None
    target: str

    def __init__(
        self,
        target: str | None = ...,
        *,
        source: str | None = ...,
    ) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...

class Purge(Component):
    namevar: str
    pattern: str

    def __init__(
        self,
        pattern: str | None = ...,
    ) -> None: ...
    @typing.override
    def configure(self) -> None: ...
    @typing.override
    def update(self) -> None: ...
    @typing.override
    def verify(self) -> None: ...
