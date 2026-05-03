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
