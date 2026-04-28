from typing import Any, Protocol

class OutputBackend(Protocol):
    def line(self, message: str, /, **fmt: object) -> None: ...
    def sep(self, sep: str, title: str, /, **fmt: object) -> None: ...
    def write(self, content: str, /, **fmt: object) -> None: ...

class TerminalBackend:
    _tw: Any  # py.io.TerminalWriter — external lib without stubs

    def __init__(self) -> None: ...
    def line(
        self,
        message: str,
        **fmt: object,
    ) -> None: ...
    def sep(
        self,
        sep: str,
        title: str,
        **fmt: object,
    ) -> None: ...
    def write(
        self,
        content: str,
        **fmt: object,
    ) -> None: ...

class NullBackend:
    def line(
        self,
        message: str,
        **fmt: object,
    ) -> None: ...
    def sep(
        self,
        sep: str,
        title: str,
        **fmt: object,
    ) -> None: ...
    def write(
        self,
        content: str,
        **fmt: object,
    ) -> None: ...

class TestBackend:
    output: str

    def __init__(self) -> None: ...
    def line(
        self,
        message: str,
        **fmt: object,
    ) -> None: ...
    def sep(
        self,
        sep: str,
        title: str,
        **fmt: object,
    ) -> None: ...
    def write(
        self,
        content: str,
        **fmt: object,
    ) -> None: ...

# The output module imports Output from remote_core
# Import at end to avoid circular import issues
from batou.remote_core import Output  # noqa: E402

output: Output
