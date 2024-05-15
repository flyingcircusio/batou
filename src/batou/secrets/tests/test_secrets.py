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
    DiffableAGEEncryptedFile,
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


def test_open_nonexistent_file_for_read_should_fail():
    with pytest.raises(IOError):
        with GPGEncryptedFile(pathlib.Path("/no/such/file")) as secret:
            secret.cleartext


def test_open_nonexistent_file_for_write_should_create_empty_lock_file():
    tf = tempfile.NamedTemporaryFile(prefix="new_encrypted.")
    tf.close()  # deletes file
    encrypted = GPGEncryptedFile(pathlib.Path(tf.name), writeable=True)
    with encrypted as secrets:
        assert secrets.cleartext == ""
        # The file exists, because we set the write lock
        assert os.path.exists(tf.name)
    # When exiting a file without writing, the lock file is removed
    assert not os.path.exists(tf.name)


def test_write(encrypted_file):
    # encrypted = EncryptedConfigFile(encrypted_file, write_lock=True)
    encrypted = GPGEncryptedFile(pathlib.Path(encrypted_file), writeable=True)
    with encrypted as secrets:
        secrets.write(
            b"""\
[batou]
members = batou
[asdf]
x = 1
""",
            ["batou"],
        )

    assert FIXTURE_ENCRYPTED_CONFIG.read_bytes() != encrypted_file.read_bytes()
    assert 0 != encrypted_file.stat().st_size


def test_write_fails_if_recipient_key_is_missing_keeps_old_file(encrypted_file):
    encrypted = GPGEncryptedFile(pathlib.Path(encrypted_file), writeable=True)
    with encrypted as secrets:
        with pytest.raises(batou.GPGCallError):
            secrets.write(
                b"""\
[batou]
members = foobar@example.com
[asdf]
x = 1
""",
                ["foobar@example.com"],
            )

    assert encrypted_file.read_bytes() == FIXTURE_ENCRYPTED_CONFIG.read_bytes()


def test_write_and_read_age_diffable(encrypted_file):
    encrypted = DiffableAGEEncryptedFile(
        pathlib.Path(encrypted_file), writeable=True
    )
    content = b"""\
[batou]
members = ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIACZ8++sQADp8fztgumfw2i+WSgzMHB7MgSpkM2y5pHi batou-ci-test-key

[asdf]
value = This is a very long
    multiline string
    that should be encrypted
    and decrypted correctly
"""
    # parse content as config to ensure that the content is valid
    config = configparser.ConfigParser()
    config.read_string(content.decode("utf-8"))

    with encrypted as secrets:
        secrets.write(
            content,
            [
                "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIACZ8++sQADp8fztgumfw2i+WSgzMHB7MgSpkM2y5pHi batou-ci-test-key"
            ],
        )

    assert content != encrypted_file.read_bytes()
    assert 0 != encrypted_file.stat().st_size

    with DiffableAGEEncryptedFile(encrypted_file) as secrets:
        # we want the multiline string to be read correctly
        secret_config = configparser.ConfigParser()
        secret_config.read_string(secrets.cleartext)
        assert config["asdf"]["value"] == secret_config["asdf"]["value"]
