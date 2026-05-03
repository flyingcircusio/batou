from collections.abc import Generator
from typing import Any

import pytest

from batou.component import RootComponent

@pytest.fixture
def root(tmpdir: Any) -> RootComponent: ...  # Any: py.path.local, deprecated fixture
@pytest.fixture(autouse=True)
def ensure_workingdir(request: pytest.FixtureRequest) -> Generator[None]: ...
@pytest.fixture(autouse=True)
def reset_resolve_overrides() -> Generator[None]: ...
def pytest_assertrepr_compare(op: object, left: object, right: object) -> list[str] | None: ...
@pytest.fixture(autouse=True)
def output(monkeypatch: pytest.MonkeyPatch) -> Any: ...  # Any: patches output module
