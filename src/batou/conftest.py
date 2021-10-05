import os.path

import pytest


@pytest.fixture(autouse=True)
def ensure_gpg_homedir(monkeypatch):
    home = os.path.join(
        os.path.dirname(__file__), 'secrets', 'tests', 'fixture', 'gnupg')
    monkeypatch.setitem(os.environ, "GNUPGHOME", home)
