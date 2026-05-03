"""Runtime gate: stubs must match the runtime package (mypy.stubtest).

Run by tox -e typing via ``pytest typing_tests/test_stubtest.py`` — unlike
test_stubs.py next to it, this file IS executed. The stub search path is
read from ``[tool.mypy] mypy_path`` (single source of truth): stubtest
does not pick up mypy_path from pyproject.toml on its own, and the
bare-invocation typing model has no MYPYPATH env or --mypy-config-file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import tomllib

REPO = Path(__file__).resolve().parents[1]


def test_stubs_match_runtime() -> None:
    mypy_config = tomllib.loads((REPO / "pyproject.toml").read_text())
    mypy_path = str(mypy_config["tool"]["mypy"]["mypy_path"])
    env = {**os.environ, "MYPYPATH": str(REPO / mypy_path)}
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy.stubtest",
            "batou",
            "--allowlist",
            str(REPO / "stubs" / "stubtest-allowlist.txt"),
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=110,
    )
    assert proc.returncode == 0, (
        f"mypy.stubtest exited {proc.returncode}:\n"
        f"{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}"
    )


def test_mypy_is_stubtest_engine_only() -> None:
    """Contract: mypy powers stubtest but has no checker gate.

    A version-identical mypy outside the pinned environment produced
    dozens of spurious errors (missing third-party stubs, foreign
    site-packages), and mypy is the only checker that needs PyPI
    companion stubs at all. The checker gate is gone; the engine
    stays, and the third-party stubs moved to the default dev group
    so every synced environment carries them.
    """
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    groups = pyproject["dependency-groups"]

    def _has(group: list[str | dict[str, str]], name: str) -> bool:
        return any(
            isinstance(dep, str) and dep.startswith(name) for dep in group
        )

    assert _has(groups["typing"], "mypy"), "stubtest needs the mypy engine"
    for stubs_pkg in ("types-mock", "types-pyyaml"):
        assert _has(groups["dev"], stubs_pkg), (
            f"{stubs_pkg} belongs in the default dev group"
        )
        assert not _has(groups["typing"], stubs_pkg), (
            f"{stubs_pkg} must move to dev, not duplicate"
        )
    mypy_config = pyproject["tool"]["mypy"]
    assert "files" not in mypy_config, (
        "[tool.mypy].files would resurrect the bare checker gate"
    )
    assert mypy_config.get("mypy_path") == "stubs"
    commands = pyproject["tool"]["tox"]["env"]["typing"]["commands"]
    assert ["mypy"] not in commands, "mypy has no checker invocation"
