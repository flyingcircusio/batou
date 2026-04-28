from typing import Literal

from batou.component import Component

class DPKG(Component):
    namevar: Literal["package"]

    def __init__(
        self,
        package: str | None = ...,
    ) -> None: ...
    def verify(self) -> None: ...
    def update(self) -> None: ...
