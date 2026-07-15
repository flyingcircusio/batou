import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

import batou.utils


def _ignore_socket_files(directory, contents):
    """Ignore socket files when copying gnupg directory."""
    dir_path = Path(directory)
    ignored = []
    for name in contents:
        path = dir_path / name
        if path.is_socket():
            ignored.append(name)
    return ignored


@pytest.fixture(autouse=True)
def ensure_gpg_homedir(monkeypatch, tmp_path_factory):
    fixture_gnupg = Path(__file__).parent / "secrets/tests/fixture/gnupg"
    with tempfile.TemporaryDirectory() as home:
        shutil.copytree(
            fixture_gnupg,
            home,
            dirs_exist_ok=True,
            ignore=_ignore_socket_files,
        )

        monkeypatch.setitem(os.environ, "GNUPGHOME", home)
        os.system(f"gpg-agent --homedir='{home}' --daemon")

        yield

        # Kill gpg-agent and clean up temp directory
        subprocess.run(
            ["gpgconf", f"--homedir='{home}", "--kill", "gpg-agent"],
            check=False,
        )


@pytest.fixture(autouse=True)
def ensure_age_identity(monkeypatch):
    key = os.path.join(
        os.path.dirname(__file__),
        "secrets",
        "tests",
        "fixture",
        "age",
        "id_ed25519",
    )
    monkeypatch.setitem(os.environ, "BATOU_AGE_IDENTITIES", key)


@pytest.fixture(autouse=True)
def ensure_git_isolated(monkeypatch):
    monkeypatch.setitem(os.environ, "GIT_CONFIG_GLOBAL", "")
    monkeypatch.setitem(os.environ, "GIT_CONFIG_SYSTEM", "")


@pytest.fixture(autouse=True)
def reset_address_defaults():
    v4, v6 = batou.utils.Address.require_v4, batou.utils.Address.require_v6
    yield
    batou.utils.Address.require_v4, batou.utils.Address.require_v6 = v4, v6


@pytest.fixture(scope="session")
def git_main_branch() -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.check_call(["git", "-C", tmpdir, "init", "."])
        return (
            subprocess.check_output(
                ["git", "-C", tmpdir, "branch", "--show-current"]
            )
            .decode("ascii")
            .strip()
        )
