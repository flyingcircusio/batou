from batou.component import Component

class Service(Component):
    executable: str
    pidfile: str | None

    def __init__(
        self,
        executable: str | None = ...,
        *,
        pidfile: str | None = ...,
    ) -> None: ...
    def start(self) -> None: ...
