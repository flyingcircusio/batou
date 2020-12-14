from batou.secrets.encryption import EncryptedConfigFile, EncryptedFile
from batou.secrets.encryption import NEW_FILE_TEMPLATE
from batou.secrets import add_secrets_to_environment
import configparser
import mock
import os
import os.path
import pytest
import shutil
import subprocess
import tempfile

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture")
cleartext_file = os.path.join(FIXTURE, "cleartext.cfg")
encrypted_file = os.path.join(FIXTURE, "encrypted.cfg")


@pytest.fixture(scope="session", autouse=True)
def cleanup_gpg_sockets():
    yield
    for path in [
            "S.dirmngr",
            "S.gpg-agent",
            "S.gpg-agent.browser",
            "S.gpg-agent.extra",
            "S.gpg-agent.ssh",]:
        try:
            os.remove(os.path.join(FIXTURE, "gnupg", path))
        except OSError:
            pass


def test_error_message_no_gpg_found():
    c = EncryptedFile(encrypted_file)
    c.GPG_BINARY_CANDIDATES = ["foobarasdf-54875982"]
    with pytest.raises(RuntimeError) as e:
        c.gpg()
    assert e.value.args[0] == (
        "Could not find gpg binary. Is GPG installed? I tried looking for: "
        "`foobarasdf-54875982`")


def test_decrypt():
    with EncryptedConfigFile(encrypted_file) as secrets:
        secrets.read()
        with open(cleartext_file) as cleartext:
            assert (cleartext.read().strip() ==
                    secrets.main_file.cleartext.strip())


def test_caches_cleartext():
    with EncryptedConfigFile(encrypted_file) as secrets:
        secrets.read()
        secrets.main_file.cleartext = "[foo]bar=2"
        secrets.read()
        assert secrets.main_file.cleartext == "[foo]bar=2"


def test_decrypt_missing_key(monkeypatch):
    monkeypatch.setitem(os.environ, "GNUPGHOME", '/tmp')

    with pytest.raises(subprocess.CalledProcessError):
        EncryptedConfigFile(encrypted_file)
        f = secrets.__enter__()
        f.read()


def test_write_should_fail_unless_write_locked():
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
        assert not secrets.main_file.cleartext
        secrets.read()
        assert secrets.main_file.cleartext == NEW_FILE_TEMPLATE
        # The file exists, because we set the write lock
        assert os.path.exists(secrets.main_file.encrypted_filename)


def test_write_unparsable_raises_error():
    with tempfile.NamedTemporaryFile(prefix="new_encrypted.") as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(tf.name, write_lock=True)
        with encrypted as secrets:
            secrets.main_file.cleartext = "some new file contents\n"
            with pytest.raises(configparser.Error):
                secrets.read()


def test_write():
    with tempfile.NamedTemporaryFile(prefix="new_encrypted.") as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(tf.name, write_lock=True)
        with encrypted as secrets:
            secrets.main_file.cleartext = """\
[batou]
members = batou
[asdf]
x = 1
"""
            secrets.read()
            secrets.write()

        with open(encrypted_file, "rb") as old:
            with open(tf.name, "rb") as new:
                assert old.read() != new.read()
        assert 0 != os.stat(tf.name).st_size


def test_write_fails_without_recipients():
    with tempfile.NamedTemporaryFile(prefix="new_encrypted.") as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(tf.name, write_lock=True)
        with encrypted as secrets:
            secrets.main_file.cleartext = """\
[batou]
members =
[asdf]
x = 1
"""
            secrets.read()
            with pytest.raises(ValueError):
                secrets.write()


def test_write_fails_if_recipient_key_is_missing_keeps_old_file():
    with tempfile.NamedTemporaryFile(prefix="new_encrypted.") as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(tf.name, write_lock=True)
        with encrypted as secrets:
            secrets.read()
            secrets.main_file.cleartext = """\
[batou]
members = foobar@example.com
[asdf]
x = 1
"""
            secrets.read()
            with pytest.raises(RuntimeError):
                secrets.write()
        with open(tf.name, "rb") as tf_h:
            with open(encrypted_file, "rb") as encrypted_h:
                assert tf_h.read() == encrypted_h.read()


def test_secrets_override_without_interpolation(tmpdir):
    os.makedirs(str(tmpdir / "secrets"))
    os.chdir(str(tmpdir))
    secret_file = str(tmpdir / "secrets" / "env.cfg")
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

        with encrypted.add_file(str(tmpdir / 'secrets' / 'env-asdf.txt')) as f:
            f.cleartext = 'hello!'

        secrets.write()

    env = mock.Mock()
    env.name = "env"
    env.components = ["asdf"]
    env.overrides = {}
    env.hosts = {}
    env.hosts["localhost"] = host = mock.Mock()
    env.secret_files = {}
    host.data = {"asdf": 1, "csdf": 3}

    add_secrets_to_environment(env)

    assert env.overrides == {"asdf": {"x": "asdf%asdf%"}}
    assert host.data == {"asdf": "2", "bsdf": "1", "csdf": "3"}
    assert env.secret_files['asdf.txt'] == 'hello!'
