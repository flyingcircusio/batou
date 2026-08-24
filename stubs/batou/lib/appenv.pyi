from typing import Literal, override

from batou.component import Component

class VirtualEnv(Component):
    namevar: Literal["python_version"]
    python_version: str
    pip_version: str | None

    def __init__(self, python_version: str | None = ..., *, pip_version: str | None = ...) -> None: ...
    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class LockedRequirements(Component):
    python: str

    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class CleanupUnused(Component):
    cleanup: tuple[str, ...]

    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class AppEnv(Component):
    namevar: Literal["python_version"]
    python_version: str
    pip_version: str | None
    env_hash: str
    env_dir: str
    env_ready: str
    last_env_hash: str | None

    @override
    def configure(self) -> None: ...
    @property
    @override
    def namevar_for_breadcrumb(self) -> str: ...
