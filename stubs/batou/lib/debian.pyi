from typing import override

import batou.lib.logrotate
import batou.lib.supervisor
from batou.component import Attribute, Component

class RebootCronjob(Component):
    @override
    def configure(self) -> None: ...

class Supervisor(batou.lib.supervisor.Supervisor):
    pidfile: Attribute[str]

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

class Logrotate(batou.lib.logrotate.Logrotate):
    common_config: bytes

    def __init__(
        self,
        *,
        common_config: bytes = ...,
    ) -> None: ...

class LogrotateCronjob(Component):
    directory: str

    @override
    def configure(self) -> None: ...
