from typing import Any, Literal

from batou.component import Component

class Configure(Component):
    namevar: Literal["path"]
    path: str
    args: str
    prefix: str | None
    build_environment: (
        dict[str, Any] | None  # Any: build env values (paths, flags, etc.)
    )

    def __init__(
        self, path: str | None = ..., *, args: str = ..., prefix: str | None = ..., build_environment: dict[str, str] | None = ...
    ) -> None: ...
    def configure(self) -> None: ...
    def update(self) -> None: ...
    def verify(self) -> None: ...

class Make(Component):
    namevar: Literal["path"]
    path: str
    build_environment: (
        dict[str, Any] | None  # Any: build env values (paths, flags, etc.)
    )

    def __init__(self, path: str | None = ..., *, build_environment: dict[str, str] | None = ...) -> None: ...
    def update(self) -> None: ...
    def verify(self) -> None: ...

class Build(Component):
    namevar: Literal["uri"]
    uri: str
    checksum: str | None  # type: ignore[assignment]
    configure_args: str
    prefix: str | None
    build_environment: (
        dict[str, Any] | None  # Any: build env values (paths, flags, etc.)
    )

    def __init__(
        self,
        uri: str | None = ...,
        *,
        checksum: str | None = ...,
        configure_args: str = ...,
        prefix: str | None = ...,
        build_environment: dict[str, str] | None = ...,
    ) -> None: ...
    def configure(self) -> None: ...
    @property
    def namevar_for_breadcrumb(self) -> str: ...
