from batou.component import Component

class UserInit(Component):
    executable: str
    pidfile: str

    def configure(self) -> None: ...
