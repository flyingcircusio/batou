from typing import Final, Literal, override

from batou.component import Component

class UseSudo:
    """Sentinel type for USE_SUDO marker."""

USE_SUDO: Final[UseSudo]

class Command(Component):
    namevar: Literal["statement"]
    admin_password: str | UseSudo | None
    admin_user: str
    hostname: str | None
    port: int | None
    db: str
    unless: str
    statement: str
    tmp: str

    def __init__(
        self,
        statement: str | None = ...,
        *,
        admin_password: str | UseSudo | None = ...,
        admin_user: str = ...,
        hostname: str | None = ...,
        port: int | None = ...,
        db: str = ...,
        unless: str = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...
    def _mysql(self, cmd: str) -> tuple[str, str]: ...
    @override
    def verify(self) -> None: ...
    @override
    def update(self) -> None: ...
    @property
    @override
    def namevar_for_breadcrumb(self) -> str: ...

class Database(Component):
    namevar: Literal["database"]
    database: str
    charset: str
    base_import_file: str | None
    admin_password: str | UseSudo | None

    def __init__(
        self,
        database: str | None = ...,
        *,
        charset: str = ...,
        base_import_file: str | None = ...,
        admin_password: str | UseSudo | None = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...

class User(Component):
    namevar: Literal["user"]
    password: str | None
    allow_from_hostname: str
    admin_password: str | UseSudo | None
    SET_PASSWORD_QUERY: Final[str]

    def __init__(
        self,
        user: str | None = ...,
        *,
        password: str | None = ...,
        allow_from_hostname: str = ...,
        admin_password: str | UseSudo | None = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...

class Grant(Command):
    namevar: Literal["grant_db"]  # type: ignore[assignment]
    user: str
    allow_from_hostname: str
    statement: str

    def __init__(
        self,
        grant_db: str | None = ...,
        *,
        admin_password: str | UseSudo | None = ...,
        admin_user: str = ...,
        hostname: str | None = ...,
        port: int | None = ...,
        db: str = ...,
        unless: str = ...,
        user: str = ...,
        allow_from_hostname: str = ...,
    ) -> None: ...
