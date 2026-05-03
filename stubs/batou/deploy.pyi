import asyncio
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from batou.environment import Environment
from batou.host import Host
from batou.utils import Timer

def main(
    environment: str,
    platform: str | None,
    timeout: int | None,
    dirty: bool,
    consistency_only: bool,
    predict_only: bool,
    check_and_predict_local: bool,
    jobs: int | None,
    provision_rebuild: bool,
) -> None: ...

class Connector(threading.Thread):
    host: Host
    deployment: Deployment
    sem: threading.Semaphore
    exc_info: tuple[type, Exception, object] | None
    errors: bytes

    def __init__(self, host: Host, sem: threading.Semaphore) -> None: ...
    def join(self) -> None: ...  # type: ignore[override]  # ty: ignore[invalid-method-override]
    def run(self) -> None: ...

class ConfigureErrors(Exception):
    errors: list[tuple[set[str], set[str] | None, Exception]]
    all_reporting_hostnames: set[str]

    def __init__(self, errors: list[tuple[set[str], set[str] | None, Exception]], all_reporting_hostnames: set[str]) -> None: ...
    def report(self) -> str: ...

class Deployment:
    environment: Environment
    dirty: bool
    consistency_only: bool
    predict_only: bool
    jobs: int | None
    timer: Timer
    taskpool: ThreadPoolExecutor | None
    loop: asyncio.AbstractEventLoop | None
    connections: list[Connector]
    _upstream: str | None

    def __init__(
        self,
        environment: Environment | str,
        platform: str | None,
        timeout: int | None,
        dirty: bool,
        jobs: int | None,
        consistency_only: bool = ...,
        predict_only: bool = ...,
        check_and_predict_local: bool = ...,
        provision_rebuild: bool = ...,
    ) -> None: ...
    def _connections(self) -> Iterator[Connector]: ...
    def _launch_components(self, todolist: dict[tuple[str, str], dict[str, Any]]) -> None: ...
    async def _deploy_component(
        self, key: tuple[str, str], info: dict[str, Any], todolist: dict[tuple[str, str], dict[str, Any]]
    ) -> None: ...
    def connect(self) -> None: ...
    def deploy(self) -> None: ...
    def disconnect(self) -> None: ...
    def load(self) -> None: ...
    @property
    def local_consistency_check(self) -> bool: ...
    def provision(self) -> None: ...
    def summarize(self) -> None: ...
