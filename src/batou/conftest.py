import os.path

import pytest

import batou.utils


@pytest.fixture(autouse=True)
def ensure_gpg_homedir(monkeypatch):
    home = os.path.join(
        os.path.dirname(__file__), "secrets", "tests", "fixture", "gnupg"
    )
    monkeypatch.setitem(os.environ, "GNUPGHOME", home)


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
