from collections.abc import Callable
from typing import Any

from batou.environment import Environment
from batou.host import RemoteHost

def cmd(
    c: str,
    *args: object,
    **kw: object,
) -> tuple[str, str]: ...
def find_line_with(prefix: str, output: str) -> str | None: ...
def hg_cmd(
    hgcmd: str,
) -> list[dict[str, Any]]: ...  # Any: mercurial log entries are dynamic

class Repository:
    environment: Environment
    root: str | None

    def __init__(self, environment: Environment) -> None: ...
    @classmethod
    def from_environment(
        cls,
        environment: Environment,
    ) -> RSyncRepository | RSyncExtRepository | NullRepository | MercurialRepository | GitRepository: ...
    def update(self, host: RemoteHost) -> None: ...
    def verify(self) -> None: ...

class NullRepository(Repository): ...

class FilteredRSync:
    IGNORE_LIST: tuple[str, ...]

    def __init__(
        self,
        *args: object,
        **kw: object,
    ) -> None: ...
    def add_target(
        self,
        gateway: object,
        destdir: str,
        finishedcallback: Callable[[], None] | None = ...,
    ) -> None: ...
    def filter(self, path: str) -> bool: ...
    def send(self, raises: bool = ...) -> None: ...

class RSyncRepository(Repository):
    def update(self, host: RemoteHost) -> None: ...
    def verify(self) -> None: ...

class RSyncExtRepository(Repository):
    IGNORE_LIST: tuple[str, ...]
    SYNC_OPTS: list[str]

    def update(self, host: RemoteHost) -> None: ...
    def verify(self) -> None: ...

class MercurialRepository(Repository):
    root: str | None
    branch: str
    subdir: str

    def __init__(self, environment: Environment) -> None: ...
    @property
    def upstream(self) -> str: ...
    def update(self, host: RemoteHost) -> None: ...
    def verify(self) -> None: ...

class MercurialPullRepository(MercurialRepository):
    def _ship(self, host: RemoteHost) -> None: ...

class MercurialBundleRepository(MercurialRepository):
    def _ship(self, host: RemoteHost) -> None: ...

class GitRepository(Repository):
    root: str | None
    branch: str
    subdir: str
    remote: str

    def __init__(self, environment: Environment) -> None: ...
    @property
    def upstream(self) -> str: ...
    def update(self, host: RemoteHost) -> None: ...
    def verify(self) -> None: ...

class GitPullRepository(GitRepository):
    def _ship(self, host: RemoteHost) -> None: ...

class GitBundleRepository(GitRepository):
    def _ship(self, host: RemoteHost) -> None: ...
