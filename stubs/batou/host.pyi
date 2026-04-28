from collections.abc import Callable
from typing import Any

import execnet
from execnet.xspec import XSpec

from batou.component import RootComponent
from batou.environment import ConfigSection, Environment
from batou.provision import Provisioner
from batou.utils import BagOfAttributes

REMOTE_OS_ENV_KEYS: tuple[str, ...]

def get_kitchen_ssh_connection_info(name: str) -> list[str]: ...
def new_ssh_args(spec: XSpec) -> list[str]: ...

class Host:
    service_user: str | None
    require_sudo: bool | None
    ignore: bool
    platform: str | None
    _provisioner: str | None
    _provision_info: dict[str, Any]  # Any: provisioner-specific data
    remap: bool
    _name: str
    aliases: BagOfAttributes
    data: dict[str, Any]  # Any: host data heterogeneous
    rpc: RPCWrapper
    environment: Environment

    @property
    def _aliases(self) -> list[str]: ...
    def __init__(
        self,
        name: str,
        environment: Environment,
        config: dict[str, Any] | ConfigSection = ...,
    ) -> None: ...
    @property
    def components(self) -> dict[str, RootComponent]: ...
    def deploy_component(self, component: str, predict_only: bool) -> None: ...
    @property
    def fqdn(self) -> str: ...
    @property
    def name(self) -> str: ...
    @property
    def provisioner(self) -> Provisioner | None: ...
    def root_dependencies(self) -> dict[tuple[str, str], dict[str, Any]]: ...
    def summarize(self) -> None: ...

class LocalHost(Host):
    gateway: execnet.Gateway
    channel: Any  # Any: execnet channel, library has no stubs
    remote_repository: Any  # Any: remote repository object
    remote_base: str

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def start(self) -> str: ...

class RPCWrapper:
    host: Host

    def __getattr__(
        self,
        name: str,
    ) -> Callable[..., Any]: ...  # Any: dynamic RPC methods
    def __init__(self, host: Host) -> None: ...

class RemoteHost(Host):
    gateway: execnet.Gateway | None
    channel: Any  # Any: execnet channel, library has no stubs
    remote_repository: Any  # Any: remote repository object
    remote_base: str

    def _makegateway(self, interpreter: str) -> Any: ...  # Any: execnet gateway
    def connect(self, interpreter: str = ...) -> None: ...
    def disconnect(self) -> None: ...
    def start(self) -> str: ...
