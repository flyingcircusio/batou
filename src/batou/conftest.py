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


@pytest.fixture(autouse=True, scope="session")
def ensure_gpg_homedir(tmp_path_factory):
    fixture_gnupg = Path(__file__).parent / "secrets/tests/fixture/gnupg"
    tmp_base = Path(__file__).parent.parent.parent / "tmp"
    tmp_base.mkdir(exist_ok=True)
    tmp_gnupg = Path(tempfile.mkdtemp(prefix="gpg-", dir=tmp_base))
    shutil.copytree(
        fixture_gnupg,
        tmp_gnupg,
        dirs_exist_ok=True,
        ignore=_ignore_socket_files,
    )
    # GPG requires strict permissions (0700) on its homedir
    tmp_gnupg.chmod(0o700)
    os.environ["GNUPGHOME"] = str(tmp_gnupg)

    yield

    # Kill gpg-agent and clean up temp directory
    subprocess.run(["gpgconf", "--kill", "gpg-agent"], check=False)
    shutil.rmtree(tmp_gnupg, ignore_errors=True)
    # Remove tmp_base if empty
    try:
        os.rmdir(tmp_base)
    except OSError:
        pass


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
