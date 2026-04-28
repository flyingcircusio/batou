import types
from typing import Final, Literal, Self, override

from batou.component import Component

class DMGVolume:
    HDIUTIL: Final[str]
    path: str
    name: str
    volume_path: str | None

    def __init__(self, path: str) -> None: ...
    def _mount(self) -> str: ...
    def _unmount(self) -> None: ...
    def copy_to(self, target_dir: str) -> None: ...
    def namelist(
        self,
    ) -> list[object]: ...

class DMGExtractor(Extractor):
    suffixes: tuple[str, ...]
    volume: DMGVolume

    @override
    def __enter__(self) -> Self: ...
    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None: ...
    def get_names_from_archive(self) -> list[str]: ...
    @override
    def update(self) -> None: ...

class Extract(Component):
    namevar: Literal["archive"]
    archive: str
    create_target_dir: bool
    target: str | None
    strip: int
    extractor: Extractor

    def __init__(
        self,
        archive: str | None = ...,
        *,
        create_target_dir: bool = ...,
        target: str | None = ...,
        strip: int = ...,
    ) -> None: ...
    @override
    def configure(self) -> None: ...
    @property
    @override
    def namevar_for_breadcrumb(self) -> str: ...

class Extractor(Component):
    namevar: Literal["archive"]
    archive: str
    target: str | None
    create_target_dir: bool
    strip: int
    _supports_strip: bool
    suffixes: tuple[str, ...]

    def __init__(
        self,
        archive: str | None = ...,
        *,
        create_target_dir: bool = ...,
        suffixes: tuple[str, ...] = ...,
        strip: int = ...,
        target: str | None = ...,
    ) -> None: ...
    @classmethod
    def can_handle(cls, archive: str) -> bool: ...
    @override
    def configure(self) -> None: ...
    @classmethod
    def extract_base_name(cls, archive: str) -> str | None: ...
    @property
    @override
    def namevar_for_breadcrumb(self) -> str: ...
    def verify(self) -> None: ...

class Untar(Extractor):
    suffixes: tuple[str, ...]
    exclude: tuple[str, ...] | str
    _supports_strip: bool

    @override
    def configure(self) -> None: ...
    def get_names_from_archive(self) -> list[str]: ...
    @override
    def update(self) -> None: ...

class Unzip(Extractor):
    suffixes: tuple[str, ...]

    def get_names_from_archive(self) -> list[str]: ...
    @override
    def update(self) -> None: ...
