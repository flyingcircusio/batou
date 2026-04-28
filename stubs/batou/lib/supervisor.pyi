from typing import Any, Literal, override

from batou.component import Attribute, Component
from batou.utils import Address

class Program(Component):
    program_section: str
    name: str
    deployment: Literal["hot", "cold"]
    command: str | None
    command_absolute: bool
    options: dict[str, Any]  # Any: supervisor program options of various types
    args: str
    priority: int
    directory: str | None
    dependencies: tuple[Component, ...] | None
    enable: bool
    supervisor: Supervisor
    config: str
    _evaded: bool

    def __init__(
        self,
        name: str | None = ...,
        *,
        deployment: str = ...,
        command: str | None = ...,
        command_absolute: bool = ...,
        options: dict[str, Any] = ...,
        args: str = ...,
        priority: int = ...,
        directory: str | None = ...,
        dependencies: list[Component] | None = ...,
        enable: bool = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...
    def ctl(
        self,
        args: str,
        **kw: object,
    ) -> tuple[str, str]: ...
    def evade(self, component: RunningSupervisor) -> None: ...
    def is_running(self) -> bool: ...
    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class Eventlistener(Program):
    program_section: str
    events: str | tuple[str, ...]
    args: str | None  # type: ignore[assignment]

    def __init__(
        self,
        name: str | None = ...,
        *,
        deployment: str = ...,
        command: str | None = ...,
        command_absolute: bool = ...,
        options: dict[str, Any] = ...,
        args: str | None = ...,
        priority: int = ...,
        directory: str | None = ...,
        dependencies: list[Component] | None = ...,
        enable: bool = ...,
        events: str | tuple[str, ...] = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...

class Supervisor(Component):
    address: Attribute[Address]
    buildout_version: Attribute[str]
    setuptools_version: Attribute[str]
    wheel_version: Attribute[str]
    packaging_version: Attribute[str]
    buildout_cfg: str
    supervisor_conf: str
    program_config_dir: Component | None
    logdir: Component | None
    loglevel: Literal["info", "debug", "warn", "error", "critical"]
    logrotate: Attribute[bool | str]
    nagios: Attribute[bool | str]
    enable: Attribute[bool | str]
    deployment_mode: Attribute[Literal["hot", "cold"]]
    max_startup_delay: Attribute[int | str]
    wait_for_running: Attribute[bool | str]
    pidfile: Attribute[str]
    socketpath: Attribute[str]
    check_contact_groups: str | None

    def __init__(
        self,
        *,
        address: str = ...,
        buildout_version: str = ...,
        setuptools_version: str = ...,
        wheel_version: str = ...,
        packaging_version: str = ...,
        logrotate: bool | str = ...,
        nagios: bool | str = ...,
        enable: bool | str = ...,
        deployment_mode: str = ...,
        max_startup_delay: int | str = ...,
        wait_for_running: bool | str = ...,
        pidfile: str = ...,
        socketpath: str = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...

class RunningHelper(Component):
    def is_running(self) -> bool: ...

class RunningSupervisor(RunningHelper):
    action: str | None
    reload_timeout: int
    service: Component

    def __init__(
        self,
        service: str | None = ...,
        *,
        action: str | None = ...,
        reload_timeout: int = ...,
    ) -> None: ...
    def reload_supervisor(self) -> None: ...
    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class StoppedSupervisor(RunningHelper):
    @override
    def verify(self) -> None: ...
    @override
    def update(self) -> None: ...
