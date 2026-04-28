from collections import defaultdict

from batou.component import RootComponent
from batou.host import Host

class Resources:
    subscribers: dict[str, set[Subscription]] | None
    dirty_dependencies: set[RootComponent]
    resources: (
        dict[
            str,
            dict[RootComponent, list[object]],
        ]
        | None
    )

    def __init__(self) -> None: ...
    def _subscriptions(self, key: str, host: Host | None) -> list[Subscription]: ...
    def copy_resources(
        self,
    ) -> dict[str, dict[RootComponent, list[object]]]: ...
    def get(
        self,
        key: str,
        host: Host | None = ...,
    ) -> list[object]: ...
    def get_dependency_graph(
        self,
    ) -> defaultdict[RootComponent, set[RootComponent]]: ...
    def provide(
        self,
        root: RootComponent,
        key: str,
        value: object,
    ) -> None: ...
    def require(
        self,
        root: RootComponent,
        key: str,
        host: Host | None = ...,
        strict: bool = ...,
        reverse: bool = ...,
        dirty: bool = ...,
    ) -> list[object]: ...
    def reset_component_resources(self, root: RootComponent) -> None: ...
    @property
    def strict_subscribers(self) -> set[Subscription]: ...
    @property
    def unsatisfied(self) -> set[tuple[str, str | None]]: ...
    @property
    def unsatisfied_components(self) -> set[RootComponent]: ...
    @property
    def unsatisfied_keys_and_components(
        self,
    ) -> dict[tuple[str, str | None], set[RootComponent]]: ...
    @property
    def unused(
        self,
    ) -> dict[str, dict[RootComponent, list[object]]]: ...

class Subscription:
    root: RootComponent
    strict: bool
    host: Host | None
    reverse: bool
    dirty: bool

    def __hash__(self) -> int: ...
    def __init__(
        self,
        root: RootComponent,
        strict: bool,
        host: Host | None,
        reverse: bool,
        dirty: bool,
    ) -> None: ...
