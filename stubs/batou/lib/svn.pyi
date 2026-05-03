from typing import Literal

from batou.component import Component

class Checkout(Component):
    namevar: Literal["url"]
    url: str
    target: str
    revision: str | None

    def __init__(self, url: str | None = ..., *, target: str = ..., revision: str | None = ...) -> None: ...
    def configure(self) -> None: ...
    def update(self) -> None: ...
    def verify(self) -> None: ...

Subversion = Checkout  # BBB
