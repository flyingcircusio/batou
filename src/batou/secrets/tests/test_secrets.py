import configparser
import os
import os.path
import pathlib
import shutil
import tempfile

import mock
import pytest

import batou
from batou.secrets import add_secrets_to_environment
from batou.secrets.encryption import (
    NEW_FILE_TEMPLATE,
    EncryptedConfigFile,
    EncryptedFile,
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
            "S.gpg-agent.ssh", ]:
        try:
            (FIXTURE / "gnupg" / path).unlink()
        except OSError:
            pass


def test_error_message_no_gpg_found(encrypted_file):
    c = EncryptedFile(encrypted_file)
    c.GPG_BINARY_CANDIDATES = ["foobarasdf-54875982"]
    with pytest.raises(RuntimeError) as e:
        c.gpg()
    assert e.value.args[0] == (
        "Could not find gpg binary. Is GPG installed? I tried looking for: "
        "`foobarasdf-54875982`")


def test_decrypt(encrypted_file):
    with EncryptedConfigFile(encrypted_file) as secrets:
        with open(cleartext_file) as cleartext:
            assert (cleartext.read().strip() ==
                    secrets.main_file.cleartext.strip())


def test_caches_cleartext(encrypted_file):
    with EncryptedConfigFile(encrypted_file) as secrets:
        secrets.main_file.cleartext = "[foo]bar=2"
        secrets.read()
        assert secrets.main_file.cleartext == "[foo]bar=2"


def test_decrypt_missing_key(monkeypatch, encrypted_file):
    monkeypatch.setitem(os.environ, "GNUPGHOME", '/tmp')

    with pytest.raises(batou.GPGCallError):
        EncryptedConfigFile(encrypted_file)


def test_write_should_fail_unless_write_locked(encrypted_file):
    with EncryptedConfigFile(encrypted_file) as secrets:
        secrets.main_file.cleartext = """\
[batou]
members = batou
[asdf]
x = 1
"""
        secrets.read()

        with pytest.raises(RuntimeError):
            secrets.write()


def test_open_nonexistent_file_for_read_should_fail():
    with pytest.raises(IOError):
        EncryptedConfigFile("/no/such/file").__enter__()


def test_open_nonexistent_file_for_write_should_create_template_file():
    tf = tempfile.NamedTemporaryFile(prefix="new_encrypted.")
    tf.close()  # deletes file
    encrypted = EncryptedConfigFile(tf.name, write_lock=True)
    with encrypted as secrets:
        assert secrets.main_file.cleartext == NEW_FILE_TEMPLATE
        # The file exists, because we set the write lock
        assert os.path.exists(secrets.main_file.encrypted_filename)
    # When saving a config without members, delete the file.
    assert not os.path.exists(secrets.main_file.encrypted_filename)


def test_write_unparsable_raises_error(encrypted_file):
    encrypted = EncryptedConfigFile(encrypted_file, write_lock=True)
    with encrypted as secrets:
        secrets.main_file.cleartext = "some new file contents\n"
        with pytest.raises(configparser.Error):
            secrets.read()


def test_write(encrypted_file):
    encrypted = EncryptedConfigFile(encrypted_file, write_lock=True)
    with encrypted as secrets:
        secrets.main_file.cleartext = """\
[batou]
members = batou
[asdf]
x = 1
"""
        secrets.read()
        secrets.write()

    assert FIXTURE_ENCRYPTED_CONFIG.read_bytes() != encrypted_file.read_bytes()
    assert 0 != encrypted_file.stat().st_size


def test_write_fails_without_recipients(encrypted_file):
    encrypted = EncryptedConfigFile(encrypted_file, write_lock=True)
    with encrypted as secrets:
        secrets.main_file.cleartext = """\
[batou]
members =
[asdf]
x = 1
"""
        secrets.read()
        with pytest.raises(ValueError) as exc:
            secrets.write()

        assert str(exc.value).startswith('Need at least one recipient.')


def test_write_fails_if_recipient_key_is_missing_keeps_old_file(
        encrypted_file):
    encrypted = EncryptedConfigFile(encrypted_file, write_lock=True)
    with encrypted as secrets:
        secrets.main_file.cleartext = """\
[batou]
members = foobar@example.com
[asdf]
x = 1
"""
        secrets.read()
        with pytest.raises(RuntimeError):
            secrets.write()
    assert encrypted_file.read_bytes() == FIXTURE_ENCRYPTED_CONFIG.read_bytes()


def test_secrets_override_without_interpolation(tmpdir):
    (tmpdir / "secrets").mkdir()
    # `add_secrets_to_environment` assumes to be run in the batou root
    os.chdir(tmpdir)
    secret_file = tmpdir / "secrets" / "env.cfg"
    encrypted = EncryptedConfigFile(secret_file, write_lock=True)

    with encrypted as secrets:
        secrets.main_file.cleartext = """\
[batou]
members = batou
[asdf]
x = asdf%asdf%
[host:localhost]
data-asdf = 2
data-bsdf = 1
data-csdf = 3
"""
        secrets.read()

        with encrypted.add_file(tmpdir / 'secrets' / 'env-asdf.txt') as f:
            f.cleartext = 'hello to me!'

        secrets.write()

    env = mock.Mock()
    env.name = "env"
    env.components = ["asdf"]
    env.overrides = {}
    env.hosts = {}
    env.hosts["localhost"] = host = mock.Mock()
    env.secret_files = {}
    env.secret_data = set()
    host.data = {"asdf": 1, "csdf": 3}

    add_secrets_to_environment(env)

    assert env.overrides == {"asdf": {"x": "asdf%asdf%"}}
    assert host.data == {"asdf": "2", "bsdf": "1", "csdf": "3"}
    assert env.secret_files['asdf.txt'] == 'hello to me!'
    assert env.secret_data == {'asdf%asdf%', 'hello', 'me!'}
