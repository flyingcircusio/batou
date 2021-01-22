import pytest
import os.path


@pytest.fixture(autouse=True)
def ensure_gpg_homedir(monkeypatch):
    home = FIXTURE = os.path.join(
        os.path.dirname(__file__), 'secrets', 'tests', 'fixture', 'gnupg')
    monkeypatch.setitem(os.environ, "GNUPGHOME", home)
