from batou.component import Component, HookComponent

class RotatedLogfile(HookComponent):
    path: str
    key: str
    args: str
    prerotate: str | None
    postrotate: str | None

    def __init__(
        self, path: str | None = ..., *, args: str = ..., prerotate: str | None = ..., postrotate: str | None = ...
    ) -> None: ...
    def configure(self) -> None: ...

class Logrotate(Component):
    common_config: bytes
    logrotate_template: bytes
    logfiles: list[RotatedLogfile]
    logrotate_conf: object  # parsed logrotate configuration object (internal)

    def __init__(self, name: str | None = ..., *, common_config: bytes = ...) -> None: ...
    def configure(self) -> None: ...

class GoceptNetRotatedLogrotate(Component):
    def configure(self) -> None: ...
