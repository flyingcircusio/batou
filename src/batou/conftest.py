import os.path
import subprocess
import tempfile

import pytest

import batou.utils


@pytest.fixture(autouse=True)
def ensure_gpg_homedir(monkeypatch):
    old_home = os.path.join(
        os.path.dirname(__file__), "secrets", "tests", "fixture", "gnupg"
    )

    with tempfile.TemporaryDirectory() as home:
        os.system(f"cp -r {old_home}/* {home}")
        os.system(f"gpg-agent --homedir='{home}' --daemon")
        monkeypatch.setitem(os.environ, "GNUPGHOME", home)

        yield

        os.system(f"gpgconf --homedir='{home}' --kill gpg-agent")


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
