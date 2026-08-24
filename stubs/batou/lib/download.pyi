from typing import Any, Literal

from batou.component import Component

class Download(Component):
    namevar: Literal["uri"]
    uri: str
    target: str | None
    checksum: str | None  # type: ignore[assignment]
    requests_kwargs: dict[str, Any] | None  # Any: arbitrary requests library kwargs
    checksum_function: str

    def __init__(
        self,
        uri: str | None = ...,
        *,
        target: str | None = ...,
        checksum: str | None = ...,
        requests_kwargs: dict[str, Any] | None = ...,
    ) -> None: ...
    def _update_requests(self) -> None: ...
    def _update_urllib(self) -> None: ...
    def configure(self) -> None: ...
    @property
    def namevar_for_breadcrumb(self) -> str: ...
    def update(self) -> None: ...
    def verify(self) -> None: ...
