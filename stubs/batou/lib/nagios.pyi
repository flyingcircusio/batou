from typing import Literal, override

from batou.component import Component, HookComponent

# Note: ServiceCheck follows batou naming convention (not PEP8)
def ServiceCheck(  # noqa: N802
    description: str,
    **kw: object,
) -> Service | NRPEService: ...

class Service(HookComponent):
    namevar: Literal["description"]
    description: str
    key: str
    command: str | None
    args: str
    notes_url: str
    servicegroups: str
    contact_groups: str | None
    depend_on: tuple[str, ...]

    def __init__(
        self,
        description: str | None = ...,
        *,
        command: str | None = ...,
        args: str = ...,
        notes_url: str = ...,
        servicegroups: str = ...,
        contact_groups: list[str] | str | None = ...,
        depend_on: tuple[tuple[Component, str], ...] = ...,
    ) -> None: ...
    @property
    def check_command(self) -> str: ...
    @override
    def configure(self) -> None: ...

class NRPEService(Service):
    name: str | None
    servicegroups: str

    def __init__(
        self,
        description: str | None = ...,
        *,
        command: str | None = ...,
        args: str = ...,
        notes_url: str = ...,
        servicegroups: str = ...,
        contact_groups: list[str] | str | None = ...,
        depend_on: tuple[tuple[Component, str], ...] = ...,
        name: str | None = ...,
    ) -> None: ...
    @property
    @override
    def check_command(self) -> str: ...
    @override
    def configure(self) -> None: ...
    @property
    def nrpe_command(self) -> str: ...

class NagiosServer(Component):
    nagios_cfg: str
    static: str
    services: list[Service]

    def __init__(
        self,
        *,
        static: str = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...

class NRPEHost(Component):
    nrpe_cfg: str
    services: list[NRPEService]

    @override
    def configure(self) -> None: ...
