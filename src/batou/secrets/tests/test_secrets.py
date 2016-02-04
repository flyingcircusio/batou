from batou.secrets.encryption import EncryptedConfigFile as BaseEncConfigFile
from batou.secrets.encryption import NEW_FILE_TEMPLATE
import ConfigParser
import os
import os.path
import pytest
import shutil
import subprocess
import tempfile


FIXTURE = os.path.join(os.path.dirname(__file__), 'fixture')
cleartext_file = os.path.join(FIXTURE, 'cleartext.cfg')
encrypted_file = os.path.join(FIXTURE, 'encrypted.cfg')


class EncryptedConfigFile(BaseEncConfigFile):

    gpg_homedir = os.path.join(FIXTURE, 'gnupg')
    gpg_opts = (BaseEncConfigFile.gpg_opts +
                ' --homedir {}'.format(gpg_homedir))


def test_decrypt():
    with EncryptedConfigFile(encrypted_file) as secrets:
        with open(cleartext_file) as cleartext:
            assert cleartext.read().strip() == secrets.read().strip()


def test_caches_cleartext():
    with EncryptedConfigFile(encrypted_file) as secrets:
        secrets.read()
        secrets._cleartext = '[foo]bar=2'
        assert secrets.read() == '[foo]bar=2'


def test_decrypt_missing_key():
    secrets = EncryptedConfigFile(
        encrypted_file)
    secrets.gpg_opts = BaseEncConfigFile.gpg_opts + ' --homedir /tmp'
    with pytest.raises(subprocess.CalledProcessError):
        f = secrets.__enter__()
        f.read()


def test_write_should_fail_unless_write_locked():
    with EncryptedConfigFile(encrypted_file) as secrets:
        with pytest.raises(RuntimeError):
            secrets.write('dummy')


def test_open_nonexistent_file_for_read_should_fail():
    with pytest.raises(IOError):
        EncryptedConfigFile('/no/such/file').__enter__()


def test_open_nonexistent_file_for_write_should_create_template_file():
    tf = tempfile.NamedTemporaryFile(prefix='new_encrypted.')
    tf.close()  # deletes file
    encrypted = EncryptedConfigFile(
        tf.name, write_lock=True)
    with encrypted as secrets:
        assert secrets.read() == NEW_FILE_TEMPLATE
        assert os.path.exists(secrets.encrypted_file)
    os.unlink(tf.name)


def test_write_unparsable_raises_error():
    with tempfile.NamedTemporaryFile(prefix='new_encrypted.') as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(
            tf.name, write_lock=True)
        with encrypted as secrets:
            with pytest.raises(ConfigParser.Error):
                secrets.write('some new file contents\n')


def test_write():
    with tempfile.NamedTemporaryFile(prefix='new_encrypted.') as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(
            tf.name, write_lock=True)
        with encrypted as secrets:
            secrets.write("""\
[batou]
members = batou
[asdf]
x = 1
""")

        with open(encrypted_file, 'rb') as old:
            with open(tf.name, 'rb') as new:
                assert old.read() != new.read()
        assert 0 != os.stat(tf.name).st_size


def test_write_fails_without_recipients():
    with tempfile.NamedTemporaryFile(prefix='new_encrypted.') as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(
            tf.name, write_lock=True)
        with encrypted as secrets:
            with pytest.raises(ValueError):
                secrets.write("""\
[batou]
members =
[asdf]
x = 1
""")


def test_write_fails_if_recipient_key_is_missing_keeps_old_file():
    with tempfile.NamedTemporaryFile(prefix='new_encrypted.') as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(
            tf.name, write_lock=True)
        with encrypted as secrets:
            with pytest.raises(RuntimeError):
                secrets.write("""\
[batou]
members = foobar@example.com
[asdf]
x = 1
""")
        assert open(tf.name).read() == open(encrypted_file).read()
