from collections import UserDict, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from batou.component import ComponentDefinition, RootComponent
from batou.host import Host
from batou.provision import Provisioner
from batou.remote_core import Deployment
from batou.repository import Repository
from batou.resources import Resources
from batou.secrets import SecretProvider

def parse_host_components(components: list[str]) -> dict[str, dict[str, Any]]: ...  # Any: host component data heterogeneous

class Config:
    def __contains__(self, section: str) -> bool: ...
    def __getitem__(self, section: str) -> ConfigSection: ...
    def __init__(self, path: Path | None) -> None: ...
    def __iter__(self) -> Iterator[str]: ...
    def get(self, section: str, default: ConfigSection | None = ...) -> ConfigSection | None: ...

class ConfigSection(UserDict[str, Any]):  # Any: heterogeneous config values
    def as_list(self, option: str) -> list[str]: ...

class Environment:
    name: str
    hosts: dict[str, Host]
    resources: Resources
    overrides: dict[str, dict[str, str]]
    secret_data: set[str]
    exceptions: list[Exception]
    timeout: int | None
    platform: str | None
    provision_rebuild: bool
    check_and_predict_local: bool
    hostname_mapping: dict[str, str]
    components: dict[str, ComponentDefinition]
    root_components: list[RootComponent]
    base_dir: str
    workdir_base: str
    secret_files: dict[str, str]
    provisioners: dict[str, Provisioner]
    service_user: str | None
    require_sudo: bool | None
    host_domain: str | None
    branch: str | None
    connect_method: Literal["local", "ssh", "vagrant", "kitchen"] | None
    update_method: (
        Literal[
            "rsync",
            "rsync-ext",
            "rsync-dev",
            "hg-bundle",
            "hg-pull",
            "git-bundle",
            "git-pull",
            "local",
        ]
        | None
    )
    vfs_sandbox: object  # VFS sandbox object, type depends on backend
    target_directory: str | None
    jobs: int | None
    require_v4: bool | Literal["optional"]
    require_v6: bool | Literal["optional"]
    repository_url: str | None
    repository_root: str | None
    host_factory: type[Host]
    repository: Repository | None
    deployment_base: str
    secret_provider: SecretProvider | None
    _toml_config: object  # TOML config object, depends on backend
    _resolve_override: dict[str, str]
    _resolve_v6_override: dict[str, str]
    deployment: Deployment | None

    def __init__(
        self,
        name: str,
        timeout: int | str | None = ...,
        platform: str | None = ...,
        basedir: str = ...,
        provision_rebuild: bool = ...,
        check_and_predict_local: bool = ...,
    ) -> None: ...
    def _ensure_environment_dir(self) -> None: ...
    def _environment_path(self, path: str = ...) -> str: ...
    def _host_data(self) -> dict[str, dict[str, Any]]: ...  # Any: host data heterogeneous
    def _load_host_components(self, host: Host, component_list: list[str]) -> None: ...
    def _load_hosts_multi_section(self, config: Config) -> None: ...
    def _load_hosts_single_section(self, config: Config) -> None: ...
    def _set_defaults(self) -> None: ...
    def add_root(
        self, component_name: str, host: Host, features: list[str] | tuple[()] = ..., ignore: bool = ...
    ) -> RootComponent: ...
    @classmethod
    def all(cls) -> Iterator[Environment]: ...
    def components_for(self, host: Host) -> dict[str, RootComponent]: ...
    def configure(self) -> list[Exception]: ...
    @classmethod
    def filter(cls, filter: str | None) -> list[Environment]: ...  # noqa: A002
    def get_host(self, hostname: str) -> Host: ...
    def get_root(self, component_name: str, host: Host) -> RootComponent: ...
    def load(self) -> None: ...
    def load_environment(self, config: Config) -> None: ...
    def load_hosts(self, config: Config) -> None: ...
    def load_provisioners(self, config: Config) -> None: ...
    def load_resolver(self, config: Config) -> None: ...
    def load_secrets(self) -> None: ...
    def map(self, path: str) -> str: ...
    def prepare_connect(self) -> None: ...
    def root_dependencies(self, host: str | None = ...) -> defaultdict[RootComponent, set[RootComponent]]: ...

class UnknownEnvironmentError(ValueError):
    names: list[str]

    def __init__(self, names: list[str]) -> None: ...
