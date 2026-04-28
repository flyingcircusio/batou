from typing import Literal, override

from batou.component import Component

class Package(Component):
    namevar: Literal["package"]
    package: str
    version: str | None
    timeout: int | None
    dependencies: bool
    env: dict[str, str] | None
    install_options: tuple[str, ...]

    def __init__(
        self,
        package: str | None = ...,
        *,
        version: str | None = ...,
        timeout: int | None = ...,
        dependencies: bool = ...,
        env: dict[str, str] | None = ...,
        install_options: tuple[str, ...] = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...
    @property
    @override
    def namevar_for_breadcrumb(self) -> str: ...
    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class VirtualEnv(Component):
    namevar: Literal["version"]
    version: str
    executable: str | None
    venv: VirtualEnvPyBase

    def __init__(
        self,
        version: str | None = ...,
        *,
        executable: str | None = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...
    @property
    def python(self) -> str: ...

class VirtualEnvDownload(Component):
    namevar: Literal["version"]
    version: str
    workdir: str | None
    checksum: str | None  # type: ignore[assignment]
    download_url: str
    venv_cmd: str

    def __init__(
        self,
        version: str | None = ...,
        *,
        checksum: str | None = ...,
        download_url: str = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...
    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class VirtualEnvPy(Component):
    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class VirtualEnvPy2_7(VirtualEnvPy):  # noqa: N801
    venv_version: str
    venv_checksum: str
    venv_options: tuple[str, ...]
    install_options: tuple[str, ...]
    pypi_url: str
    base: VirtualEnvDownload

    @override
    def configure(self) -> None: ...
    @override
    def update(self) -> None: ...
    @override
    def verify(self) -> None: ...

class VirtualEnvPyBase(Component):
    venv_version: str | None
    venv_checksum: str | None
    venv_options: tuple[str, ...]
    installer: Literal["pip", "easy_install"]
    install_options: tuple[str, ...]

    def easy_install(self, pkg: Package) -> None: ...
    def pip_install(self, pkg: Package) -> None: ...
    @override
    def update(self) -> None: ...
    def update_pkg(self, pkg: Package) -> None: ...
    @override
    def verify(self) -> None: ...
    def verify_pkg(self, pkg: Package) -> None: ...
