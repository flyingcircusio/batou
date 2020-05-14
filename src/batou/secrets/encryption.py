from batou import FileLockedError
import configparser
import fcntl
import io
import os
import subprocess
import tempfile


# https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
NULL = tempfile.TemporaryFile()


NEW_FILE_TEMPLATE = """\
[batou]
members =
"""


class EncryptedConfigFile(object):
    """Wrap encrypted config files."""

    lockfd = None
    _cleartext = None

    # Additional GPG parameters. Used for testing.
    gpg_opts = ''

    def __init__(self, encrypted_file, write_lock=False, quiet=False):
        """Context manager that opens an encrypted file.

        Use the read() and write() methods in the subordinate "with"
        block to manipulate cleartext content. If the cleartext content
        has been replaced, the encrypted file is updated.

        `write_lock` must be set True if a modification of the file is
        intended.
        """
        self.encrypted_file = encrypted_file
        self.write_lock = write_lock
        self.quiet = quiet

    def __enter__(self):
        self._lock()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        self.lockfd.close()

    def gpg(self, cmdline):
        null = tempfile.TemporaryFile()
        for gpg in ['gpg2', 'gpg']:
            try:
                subprocess.check_call(
                    [gpg, '--version'],
                    stdout=null, stderr=null)
            except (subprocess.CalledProcessError, OSError):
                pass
            else:
                return '{} {}'.format(gpg, cmdline)

    @property
    def cleartext(self):
        if self._cleartext is None:
            return NEW_FILE_TEMPLATE
        return self._cleartext

    @cleartext.setter
    def cleartext(self, value):
        self.config = configparser.RawConfigParser()
        self.config.read_string(value)
        self.set_members(self.get_members())
        s = io.StringIO()
        self.config.write(s)
        self._cleartext = s.getvalue()

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

    def write_config(self):
        s = io.StringIO()
        self.config.write(s)
        self.write(s.getvalue())

    def _lock(self):
        self.lockfd = open(
            self.encrypted_file, self.write_lock and 'a+' or 'r+')
        try:
            if self.write_lock:
                fcntl.lockf(self.lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                fcntl.lockf(self.lockfd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            raise FileLockedError(self.encrypted_file)

    def _decrypt(self):
        opts = self.gpg_opts
        if self.quiet:
            opts += ' -q --no-tty --batch'
        self.cleartext = subprocess.check_output(
            [self.gpg('{} --decrypt {}'.format(
                opts, self.encrypted_file))],
            stderr=NULL,
            shell=True).decode('utf-8')

    def get_members(self):
        members = self.config.get('batou', 'members').split(',')
        members = [x.strip() for x in members]
        members = [_f for _f in members if _f]
        members.sort()
        return members

    def set_members(self, members):
        # The whitespace here is exactly what
        # "members = " looks like in the config file so we get
        # proper indentation.
        members = ',\n      '.join(members)
        self.config.set('batou', 'members', members)

    def _encrypt(self):
        recipients = self.get_members()
        if not recipients:
            raise ValueError("Need at least one recipient.")
        self.set_members(self.get_members())
        recipients = ' '.join(['-r {}'.format(r.strip()) for r in recipients])
        os.rename(self.encrypted_file,
                  self.encrypted_file + '.old')
        try:
            gpg = subprocess.Popen(
                [self.gpg('{} --encrypt {} -o {}'.format(
                    self.gpg_opts, recipients, self.encrypted_file))],
                stdin=subprocess.PIPE,
                shell=True)
            gpg.communicate(self.cleartext.encode('utf-8'))
            if gpg.returncode != 0:
                raise RuntimeError('GPG returned non-zero exit code.')
        except Exception:
            os.rename(self.encrypted_file + '.old',
                      self.encrypted_file)
            raise
        else:
            os.unlink(self.encrypted_file + '.old')
