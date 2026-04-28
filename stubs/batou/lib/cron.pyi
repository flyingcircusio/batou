from typing import Any

from batou.component import Attribute, Component, ConfigString, HookComponent

class CronJob(HookComponent):
    command: str
    key: str
    args: str
    timing: str | None
    logger: str | None

    def __init__(
        self,
        command: str | None = ...,
        *,
        args: str = ...,
        timing: str | None = ...,
        logger: str | None = ...,
    ) -> None: ...
    def format(self) -> str: ...

def ignore_comments(data: bytes) -> bytes: ...

class CronTab(Component):
    crontab_template: str
    mailto: Attribute[str | None]
    purge: bool
    env: Attribute[dict[str, Any]]  # Any: environment variable values of various types
    jobs: list[CronJob] | None
    crontab: object  # parsed crontab object (internal)

    def __init__(
        self,
        *,
        mailto: str | None = ...,
        purge: bool = ...,
        env: str | ConfigString = ...,
    ) -> None: ...
    def configure(self) -> None: ...

class PurgeCronTab(Component):
    def configure(self) -> None: ...

class InstallCrontab(Component):
    crontab: object  # parsed crontab object (internal)

    def configure(self) -> None: ...
    def verify(self) -> None: ...
    def update(self) -> None: ...

class DebianInstallCrontab(InstallCrontab): ...
class FCInstallCrontab(InstallCrontab): ...
