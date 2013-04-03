from __future__ import print_function, unicode_literals
import fcntl
import hashlib
import os
import subprocess
import sys


class EncryptedConfigFile(object):
    """Wrap encrypted config files."""

    lockfd = None

    def __init__(self, encrypted_file, passphrase, write_lock=False):
        """Context manager that opens an encrypted file.

        Use the read() and write() methods in the subordinate "with"
        block to manipulate cleartext content. If the cleartext content
        has been replaced, the encrypted file is updated.

        `write_lock` must be set True if a modification of the file is
        intended.
        """
        self.encrypted_file = encrypted_file
        self.passphrase = passphrase
        self.write_lock = write_lock
        self.cleartext = ''

    def _run_cipher(self, method, operation_name):
        """Call cipher operation with proper error handling.

        The actual cipher is run by calling `method` without parameters.
        `operation_name` is the cipher operation in cleartext to construct
        helpful user messages.
        """
        try:
            method()
        except OSError:
            print('cannot invoke encryption utility -- '
                  'are all dependencies installed?', file=sys.stderr)
            raise
        except subprocess.CalledProcessError as e:
            raise RuntimeError('cannot %s' % operation_name,
                               self.encrypted_file, e)

    def __enter__(self):
        self._lock()
        if not os.stat(self.encrypted_file).st_size:
            return self
        self._run_cipher(self._decrypt, 'decrypt')
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.lockfd.close()

    def read(self):
        """Return decrypted content as string.

        The return value is undefined after write() has been called.
        """
        return self.cleartext

    def write(self, new_cleartext):
        """Replace encrypted file with new content."""
        if not self.write_lock:
            raise RuntimeError('write() needs a write lock')
        self._run_cipher(lambda: self._encrypt(new_cleartext), 'encrypt')

    def _lock(self):
        self.lockfd = open(
            self.encrypted_file, self.write_lock and 'a+' or 'r+')
        if self.write_lock:
            fcntl.lockf(self.lockfd, fcntl.LOCK_EX)
        else:
            fcntl.lockf(self.lockfd, fcntl.LOCK_SH)

    def _hash(self, cleartext):
        checksum = hashlib.sha1()
        checksum.update(cleartext)
        return checksum.hexdigest()

    def _decrypt(self):
        in_fd, out_fd = os.pipe()
        os.write(out_fd, self.passphrase)
        os.close(out_fd)
        with open(self.encrypted_file, 'rb') as enc:
            cleartext = subprocess.check_output(
                ['aespipe', '-d', '-p{}'.format(in_fd)], stdin=enc
            ).strip(b'\0')
        try:
            checksum, cleartext = cleartext.split(b'\n', 1)
        except ValueError:
            raise RuntimeError('wrong passphrase (cannot find checksum)')
        if checksum != self._hash(cleartext):
            raise RuntimeError('wrong passphrase (checksum mismatch)')
        self.cleartext = cleartext

    def _encrypt(self, cleartext):
        cleartext = self._hash(cleartext) + b'\n' + cleartext
        in_fd, out_fd = os.pipe()
        os.write(out_fd, self.passphrase)
        os.close(out_fd)
        with open(self.encrypted_file, 'wb') as enc:
            pipe = subprocess.Popen(
                ['aespipe', '-p{}'.format(in_fd)], stdin=subprocess.PIPE,
                stdout=enc)
            pipe.communicate(cleartext)
