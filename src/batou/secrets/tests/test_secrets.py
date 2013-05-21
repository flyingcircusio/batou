from __future__ import print_function, unicode_literals
from batou.lib.secrets.encryption import EncryptedConfigFile
from batou.tests import TestCase
import os
import os.path
import shutil
import tempfile


class EncryptedConfigFileTests(TestCase):

    def setUp(self):
        self.cleartext = (os.path.dirname(__file__) +
                          '/fixture/secrets/cleartext.cfg')
        self.encrypted = (os.path.dirname(__file__) +
                          '/fixture/secrets/encrypted.cfg')
        self.passphrase = 'SecretTestPassphrase'

    def test_decrypt(self):
        with EncryptedConfigFile(self.encrypted, self.passphrase) as secrets:
            with open(self.cleartext) as cleartext:
                self.assertEqual(cleartext.read(), secrets.read())

    def test_decrypt_wrong_passphrase(self):
        with self.assertRaises(RuntimeError):
            encrypted_file = EncryptedConfigFile(
                self.encrypted, 'incorrect passphrase')
            encrypted_file.__enter__()

    def test_write_should_fail_unless_write_locked(self):
        with EncryptedConfigFile(self.encrypted, self.passphrase) as secrets:
            self.assertRaises(RuntimeError, secrets.write, 'dummy')

    def test_open_nonexistent_file_for_read_should_fail(self):
        with self.assertRaises(IOError):
            EncryptedConfigFile('/no/such/file', self.passphrase).__enter__()

    def test_open_nonexistent_file_for_write_should_create_empty_file(self):
        tf = tempfile.NamedTemporaryFile(prefix='new_encrypted.')
        tf.close()  # deletes file
        encrypted_file = EncryptedConfigFile(
            tf.name, self.passphrase, write_lock=True)
        with encrypted_file as ef:
            self.assertEqual('', ef.read())
            self.assertFileExists(ef.encrypted_file)
        os.unlink(tf.name)

    def test_write(self):
        with tempfile.NamedTemporaryFile(prefix='new_encrypted.') as tf:
            shutil.copy(self.encrypted, tf.name)
            encrypt_file = EncryptedConfigFile(tf.name, self.passphrase,
                                               write_lock=True)
            with encrypt_file as ef:
                ef.write('some new file contents\n')
            with open(self.encrypted, 'rb') as old:
                with open(tf.name, 'rb') as new:
                    self.assertNotEqual(old.read(), new.read())
            self.assertNotEqual(0, os.stat(tf.name).st_size)
