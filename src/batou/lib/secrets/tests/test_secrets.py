# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.secrets import SecretsFile
from batou.tests import TestCase
import os
import os.path
import shutil
import tempfile


class SecretsFileTests(TestCase):

    def setUp(self):
        self.cleartext = (os.path.dirname(__file__) +
                          '/fixture/secrets/cleartext.cfg')
        self.encrypted = (os.path.dirname(__file__) +
                          '/fixture/secrets/encrypted.cfg')
        pf = tempfile.NamedTemporaryFile(prefix='passphrase.', delete=False)
        print('SecretTestPassphrase', file=pf)
        pf.close()
        self.passphrase = pf.name

    def tearDown(self):
        os.unlink(self.passphrase)

    def test_decrypt(self):
        with SecretsFile(self.encrypted, self.passphrase) as secrets:
            with open(self.cleartext) as cleartext:
                self.assertEqual(cleartext.read(), secrets.read())

    def test_decrypt_wrong_passphrase(self):
        with open(self.passphrase, 'w') as pf:
            print('wrong passphrase wrong passphrase', file=pf)
            pf.flush()
        with self.assertRaises(RuntimeError):
            with SecretsFile(self.encrypted, self.passphrase) as secrets:
                print(secrets.read())

    def test_write_should_fail_unless_write_locked(self):
        with SecretsFile(self.encrypted, self.passphrase) as secrets:
            self.assertRaises(RuntimeError, secrets.write, 'dummy')

    def test_open_nonexistent_file_for_read_should_fail(self):
        with self.assertRaises(IOError):
            with SecretsFile('/no/such/file', self.passphrase):
                pass

    def test_open_nonexistent_file_for_write_should_create_empty_file(self):
        tf = tempfile.NamedTemporaryFile(prefix='new_encrypted.')
        tf.close()  # deletes file
        with SecretsFile(tf.name, self.passphrase, write_lock=True) as sf:
            self.assertEqual('', sf.read())
            self.assertFileExists(sf.encrypted_file)
        os.unlink(tf.name)

    def test_write(self):
        with tempfile.NamedTemporaryFile(prefix='new_encrypted.') as tf:
            shutil.copy(self.encrypted, tf.name)
            with SecretsFile(tf.name, self.passphrase, write_lock=True) as sf:
                sf.write('some new file contents\n')
            with open(self.encrypted, 'rb') as old:
                with open(tf.name, 'rb') as new:
                    self.assertNotEqual(old.read(), new.read())
            self.assertNotEqual(0, os.stat(tf.name).st_size)
