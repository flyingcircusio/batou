from __future__ import print_function, unicode_literals
import ConfigParser
import StringIO
import fcntl
import hashlib
import os
import subprocess
import sys


class EncryptedConfigFile(object):
    """Wrap encrypted config files."""

    lockfd = None
    _cleartext = None

    def __init__(self, encrypted_file, write_lock=False):
        """Context manager that opens an encrypted file.

        Use the read() and write() methods in the subordinate "with"
        block to manipulate cleartext content. If the cleartext content
        has been replaced, the encrypted file is updated.

        `write_lock` must be set True if a modification of the file is
        intended.
        """
        self.encrypted_file = encrypted_file
        self.write_lock = write_lock

    def __enter__(self):
        self._lock()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.lockfd.close()

    @property
    def cleartext(self):
        if self._cleartext is None:
            return '[batou]\nmembers = \n'
        return self._cleartext

    @cleartext.setter
    def cleartext(self, value):
        self._cleartext = value
        self.config = ConfigParser.ConfigParser()
        self.config.readfp(StringIO.StringIO(value))

    def read(self):
        if self._cleartext is None:
            if os.stat(self.encrypted_file).st_size:
                self._decrypt()
        return self.cleartext

    def write(self, cleartext):
        """Replace encrypted file with new content."""
        if not self.write_lock:
            raise RuntimeError('write() needs a write lock')
        self.cleartext = cleartext
        self._encrypt()

    def _lock(self):
        self.lockfd = open(
            self.encrypted_file, self.write_lock and 'a+' or 'r+')
        if self.write_lock:
            fcntl.lockf(self.lockfd, fcntl.LOCK_EX)
        else:
            fcntl.lockf(self.lockfd, fcntl.LOCK_SH)

    def _decrypt(self):
        self.cleartext = subprocess.check_output(
            ['gpg --decrypt {}'.format(self.encrypted_file)], shell=True)

    def _encrypt(self):
        recipients = self.config.get('batou', 'members').split(',')
        recipients = ' '.join(['-r {}'.format(r.strip()) for r in recipients])
        os.rename(self.encrypted_file, self.encrypted_file+'.old')
        try:
            pipe = subprocess.Popen(
                ['gpg --batch --encrypt {} -o {}'.format(recipients, self.encrypted_file)],
                stdin=subprocess.PIPE, shell=True)
            pipe.communicate(self.cleartext)
        except Exception:
            os.rename(self.encrypted_file+'.old', self.encrypted_file)
        else:
            os.unlink(self.encrypted_file+'.old')
