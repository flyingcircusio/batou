from batou.environment import ConfigSection, Environment

class Map:
    _map: list[tuple[str, str]]

    def __init__(
        self,
        environment: Environment,
        config: ConfigSection | None,
    ) -> None: ...
    def map(self, path: str) -> str: ...

class Developer:
    environment: Environment

    def __init__(
        self,
        environment: Environment,
        config: ConfigSection | None,
    ) -> None: ...
    def map(self, path: str) -> str: ...
