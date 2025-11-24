import importlib
import sys

import pytest


@pytest.mark.skipif(
    not importlib.util.find_spec("pyrage"), reason="requires pyrage"
)
def test_import_pyrage_encryption():
    from ..secrets.encryption import EncryptedFile

    assert (
        EncryptedFile.__module__ == "batou.secrets.encryption.pyrage_encryption"
    )


def test_import_legacy_encryption(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyrage", None)

    sys.modules.pop("batou.secrets.encryption", None)
    from ..secrets.encryption import EncryptedFile

    assert EncryptedFile.__module__ == "batou.secrets.encryption.age_shellout"
