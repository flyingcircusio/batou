from batou.secrets.encryption import EncryptedConfigFile as BaseEncConfigFile
from batou.secrets.encryption import NEW_FILE_TEMPLATE
from batou.secrets import add_secrets_to_environment_override
import configparser
import mock
import os
import os.path
import pytest
import shutil
import subprocess
import tempfile


FIXTURE = os.path.join(os.path.dirname(__file__), 'fixture')
cleartext_file = os.path.join(FIXTURE, 'cleartext.cfg')
encrypted_file = os.path.join(FIXTURE, 'encrypted.cfg')


@pytest.fixture(scope='session', autouse=True)
def cleanup_gpg_sockets():
    yield
    for path in [
            'S.dirmngr',
            'S.gpg-agent',
            'S.gpg-agent.browser',
            'S.gpg-agent.extra',
            'S.gpg-agent.ssh']:
        try:
            os.remove(os.path.join(FIXTURE, 'gnupg', path))
        except OSError:
            pass


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
            with pytest.raises(configparser.Error):
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
        assert open(tf.name, 'rb').read() == open(encrypted_file, 'rb').read()


def test_secrets_override_without_interpolation(tmpdir):
    os.makedirs(str(tmpdir / 'secrets'))
    os.chdir(str(tmpdir))
    secret_file = str(tmpdir / 'secrets' / 'env.cfg')
    encrypted = EncryptedConfigFile(secret_file, write_lock=True)
    with encrypted as secrets:
        secrets.write("""\
[batou]
members = batou
[asdf]
x = asdf%asdf%
[host:localhost]
data-asdf = 2
data-bsdf = 1
data-csdf = 3
""")

    env = mock.Mock()
    env.name = 'env'
    env.components = ['asdf']
    env.overrides = {}
    env.hosts = {}
    env.hosts['localhost'] = host = mock.Mock()
    host.data = {'asdf': 1, 'csdf': 3}

    add_secrets_to_environment_override(
        env, enc_file_class=EncryptedConfigFile)

    assert env.overrides == {'asdf': {'x': 'asdf%asdf%'}}
    assert host.data == {'asdf': '2', 'bsdf': '1', 'csdf': '3'}
