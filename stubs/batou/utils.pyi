import re
import subprocess
import types
from collections import UserDict, defaultdict
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from typing import Any, Final, Literal, overload

# Module variables
notify: Callable[[str, str], None]
resolve_override: dict[str, str]
resolve_v6_override: dict[str, str]
ADDR_DEFAULT: Final[object]
VARNAME_PATTERN: re.Pattern[str]

def call_with_optional_args(
    func: Callable[..., object],
    **kw: object,
) -> object: ...
@overload
def cmd(
    cmd: str | list[str],
    silent: bool = ...,
    ignore_returncode: bool = ...,
    communicate: Literal[True] = ...,
    env: dict[str, str] | None = ...,
    acceptable_returncodes: Sequence[int] = ...,
    encoding: str | None = ...,
) -> tuple[str, str]: ...
@overload
def cmd(
    cmd: str | list[str],
    silent: bool = ...,
    ignore_returncode: bool = ...,
    communicate: Literal[False] = ...,
    env: dict[str, str] | None = ...,
    acceptable_returncodes: Sequence[int] = ...,
    encoding: str | None = ...,
) -> subprocess.Popen[str]: ...
def dict_merge(
    a: dict[str, Any],
    b: dict[str, Any],
) -> dict[str, Any]: ...  # Any: merges heterogeneous dicts
def ensure_graph_data(
    graph: defaultdict[object, set[object]],
) -> defaultdict[object, set[object]]: ...
def escape_macosx_string(s: str) -> str: ...
def export_environment_variables(environ: dict[str, str]) -> str: ...
def flatten(
    list_of_lists: list[list[object]],
) -> list[object]: ...
def format_duration(duration: float | None) -> str: ...
def get_output(command: str, default: str | None = ...) -> str: ...
def hash(path: str | bytes, function: str = ...) -> str: ...  # noqa: A001
def locked(
    filename: str,
    exit_on_failure: bool = ...,
) -> AbstractContextManager[None]: ...
def notify_macosx(title: str, description: str) -> None: ...
def notify_none(title: str, description: str) -> None: ...
def notify_send(title: str, description: str) -> None: ...
def remove_nodes_without_outgoing_edges(graph: defaultdict[object, set[object]]) -> None: ...
def resolve(
    host: str,
    port: int = ...,
    resolve_override: dict[str, str] = ...,
) -> str: ...
def resolve_v6(
    host: str,
    port: int = ...,
    resolve_override: dict[str, str] = ...,
) -> str: ...
def revert_graph(graph: defaultdict[object, set[object]]) -> defaultdict[object, set[object]]: ...
def self_id() -> str: ...
def topological_sort(
    graph: defaultdict[object, set[object]],
) -> list[object]: ...

class Address:
    connect: NetLoc
    require_v4: Literal["optional"] | bool
    require_v6: Literal["optional"] | bool

    def __init__(
        self,
        connect_address: str,
        port: int | str | None = ...,
        require_v4: Literal["optional"] | bool = ...,
        require_v6: Literal["optional"] | bool = ...,
    ) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __le__(self, other: object) -> bool: ...
    def __lt__(self, other: object) -> bool: ...
    def __gt__(self, other: object) -> bool: ...
    def __ge__(self, other: object) -> bool: ...
    @property
    def listen(self) -> NetLoc | None: ...
    @listen.setter
    def listen(self, value: NetLoc | None) -> None: ...
    @property
    def listen_v6(self) -> NetLoc | None: ...
    @listen_v6.setter
    def listen_v6(self, value: NetLoc | None) -> None: ...

class BagOfAttributes(UserDict[str, Any]):  # Any: dynamic attribute storage
    def __getattr__(self, key: str) -> Any: ...  # Any: dynamic attribute values

class CmdExecutionError(Exception):
    cmd: str
    returncode: int
    stdout: str
    stderr: str

    def __init__(
        self,
        cmd: str,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None: ...
    def report(self) -> str: ...

class CycleError(ValueError): ...

class MultiFile:
    files: list[object]

    def __init__(
        self,
        files: list[object],
    ) -> None: ...
    def flush(self) -> None: ...
    def write(self, value: str) -> None: ...

class NetLoc:
    host: str
    port: int | str | None

    def __init__(self, host: str, port: int | str | None = ...) -> None: ...
    def __eq__(self, other: object) -> bool: ...
    def __le__(self, other: object) -> bool: ...
    def __lt__(self, other: object) -> bool: ...
    def __gt__(self, other: object) -> bool: ...
    def __ge__(self, other: object) -> bool: ...

class Timer:
    durations: dict[str, float]
    tag: str | None

    def __init__(self, tag: str | None = ...) -> None: ...
    def above_threshold(self, **thresholds: float) -> tuple[bool, list[str]]: ...
    def humanize(self, *steps: str) -> str: ...
    def step(self, note: str) -> Timer.TimerContext: ...

    class TimerContext:
        timer: Timer
        note: str
        start: float

        def __enter__(self) -> None: ...
        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: types.TracebackType | None,
        ) -> None: ...
        def __init__(self, timer: Timer, note: str) -> None: ...
