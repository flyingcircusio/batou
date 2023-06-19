import configparser
import os
import os.path
import pathlib
import shutil
import tempfile

import mock
import pytest

import batou
from batou.secrets import GPGSecretProvider
from batou.secrets.encryption import (
    AGEEncryptedFile,
    EncryptedFile,
    GPGEncryptedFile,
)

FIXTURE = pathlib.Path(__file__).parent / "fixture"
cleartext_file = FIXTURE / "cleartext.cfg"
FIXTURE_ENCRYPTED_CONFIG = FIXTURE / "encrypted.cfg"


@pytest.fixture(scope="function")
def encrypted_file(tmpdir):
    """Provide a temporary copy of the encrypted confi."""
    return pathlib.Path(shutil.copy(FIXTURE_ENCRYPTED_CONFIG, tmpdir))


@pytest.fixture(scope="session", autouse=True)
def cleanup_gpg_sockets():
    yield
    for path in [
        "S.dirmngr",
        "S.gpg-agent",
        "S.gpg-agent.browser",
        "S.gpg-agent.extra",
        "S.gpg-agent.ssh",
    ]:
        try:
            (FIXTURE / "gnupg" / path).unlink()
        except OSError:
            pass


def test_error_message_no_gpg_found(encrypted_file):
    c = GPGEncryptedFile(encrypted_file)
    OLD_GPG_BINARY_CANDIDATES = GPGEncryptedFile.GPG_BINARY_CANDIDATES
    GPGEncryptedFile.GPG_BINARY_CANDIDATES = ["foobarasdf-54875982"]
    GPGEncryptedFile._gpg = None
    with pytest.raises(RuntimeError) as e:
        c.gpg()
    assert e.value.args[0] == (
        "Could not find gpg binary. Is GPG installed? I tried looking for: "
        "`foobarasdf-54875982`"
    )
    GPGEncryptedFile.GPG_BINARY_CANDIDATES = OLD_GPG_BINARY_CANDIDATES


def test_error_message_no_age_found(encrypted_file):
    c = AGEEncryptedFile(encrypted_file)
    OLD_AGE_BINARY_CANDIDATES = AGEEncryptedFile.AGE_BINARY_CANDIDATES
    AGEEncryptedFile.AGE_BINARY_CANDIDATES = ["foobarasdf-54875982"]
    AGEEncryptedFile._age = None
    with pytest.raises(RuntimeError) as e:
        c.age()
    assert e.value.args[0] == (
        "Could not find age binary. Is age installed? I tried looking for: "
        "`foobarasdf-54875982`"
    )
    AGEEncryptedFile.AGE_BINARY_CANDIDATES = OLD_AGE_BINARY_CANDIDATES


def test_decrypt(encrypted_file):
    with GPGEncryptedFile(encrypted_file) as secret:
        with open(cleartext_file) as cleartext:
            assert cleartext.read().strip() == secret.cleartext.strip()


def test_decrypt_missing_key(monkeypatch, encrypted_file):
    monkeypatch.setitem(os.environ, "GNUPGHOME", "/tmp")

    with pytest.raises(batou.GPGCallError):
        with GPGEncryptedFile(encrypted_file) as secret:
            secret.cleartext


def test_write_should_fail_unless_write_locked(encrypted_file):
    with GPGEncryptedFile(encrypted_file) as secret:
        secret.cleartext
        with pytest.raises(RuntimeError):
            secret.write(b"", [])
