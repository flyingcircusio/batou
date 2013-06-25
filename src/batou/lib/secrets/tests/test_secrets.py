from batou.lib.secrets.encryption import EncryptedConfigFile
import os
import os.path
import pytest
import shutil
import tempfile


cleartext_file = (os.path.dirname(__file__) + '/fixture/secrets/cleartext.cfg')
encrypted_file = (os.path.dirname(__file__) + '/fixture/secrets/encrypted.cfg')
passphrase = 'SecretTestPassphrase'


@pytest.mark.aespipe
def test_decrypt():
    with EncryptedConfigFile(encrypted_file, passphrase) as secrets:
        with open(cleartext_file) as cleartext:
            assert cleartext.read() == secrets.read()


@pytest.mark.aespipe
def test_decrypt_wrong_passphrase():
    secrets = EncryptedConfigFile(
        encrypted_file, 'incorrect passphrase')
    with pytest.raises(RuntimeError):
        secrets.__enter__()


@pytest.mark.aespipe
def test_write_should_fail_unless_write_locked():
    with EncryptedConfigFile(encrypted_file, passphrase) as secrets:
        with pytest.raises(RuntimeError):
            secrets.write('dummy')


def test_open_nonexistent_file_for_read_should_fail():
    with pytest.raises(IOError):
        EncryptedConfigFile('/no/such/file', passphrase).__enter__()


def test_open_nonexistent_file_for_write_should_create_empty_file():
    tf = tempfile.NamedTemporaryFile(prefix='new_encrypted.')
    tf.close()  # deletes file
    encrypted = EncryptedConfigFile(
        tf.name, passphrase, write_lock=True)
    with encrypted as secrets:
        assert '' == secrets.read()
        assert os.path.exists(secrets.encrypted_file)
    os.unlink(tf.name)


@pytest.mark.aespipe
def test_write():
    with tempfile.NamedTemporaryFile(prefix='new_encrypted.') as tf:
        shutil.copy(encrypted_file, tf.name)
        encrypted = EncryptedConfigFile(
            tf.name, passphrase, write_lock=True)
        with encrypted as secrets:
            secrets.write('some new file contents\n')
        with open(encrypted_file, 'rb') as old:
            with open(tf.name, 'rb') as new:
                assert old.read() != new.read()
        assert 0 != os.stat(tf.name).st_size
