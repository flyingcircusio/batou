from typing import Literal

from batou.component import Component

class VirtualEnv(Component):
    namevar: Literal["python_version"]
    python_version: str
    pip_version: str | None

    def __init__(self, python_version: str | None = ..., *, pip_version: str | None = ...) -> None: ...
    def update(self) -> None: ...
    def verify(self) -> None: ...

class LockedRequirements(Component):
    python: str

    def update(self) -> None: ...
    def verify(self) -> None: ...

class CleanupUnused(Component):
    cleanup: tuple[str, ...]

    def update(self) -> None: ...
    def verify(self) -> None: ...

class AppEnv(Component):
    namevar: Literal["python_version"]
    python_version: str
    pip_version: str | None
    env_hash: str
    env_dir: str
    env_ready: str
    last_env_hash: str | None

    def configure(self) -> None: ...
    @property
    def namevar_for_breadcrumb(self) -> str: ...
