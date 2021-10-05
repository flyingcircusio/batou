import fcntl
import glob
import io
import os
import subprocess
import tempfile

from configupdater import ConfigUpdater

from batou import FileLockedError, GPGCallError

# https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
NULL = tempfile.TemporaryFile()

NEW_FILE_TEMPLATE = """\
[batou]
members =
"""


class EncryptedFile(object):
    """Basic encryption methods - key management handled externally."""

    lockfd = None
    cleartext = None

    GPG_BINARY_CANDIDATES = ["gpg", "gpg2"]

    def __init__(self, encrypted_filename, write_lock=False, quiet=False):
        """Context manager that opens an encrypted file.

        Use the read() and write() methods in the subordinate "with"
        block to manipulate cleartext content. If the cleartext content
        has been replaced, the encrypted file is updated.

        `write_lock` must be set True if a modification of the file is
        intended.
        """
        # Ensure compatibility with pathlib.
        self.encrypted_filename = str(encrypted_filename)
        self.write_lock = write_lock
        self.quiet = quiet
        self.recipients = []

    def __enter__(self):
        self._lock()
        return self

    def __exit__(self, _exc_type=None, _exc_value=None, _traceback=None):
        self.lockfd.close()

    def gpg(self):
        with tempfile.TemporaryFile() as null:
            for gpg in self.GPG_BINARY_CANDIDATES:
                try:
                    subprocess.check_call([gpg, "--version"],
                                          stdout=null,
                                          stderr=null)
                except (subprocess.CalledProcessError, OSError):
                    pass
                else:
                    return gpg
        raise RuntimeError("Could not find gpg binary."
                           " Is GPG installed? I tried looking for: {}".format(
                               ", ".join("`{}`".format(x)
                                         for x in self.GPG_BINARY_CANDIDATES)))

    def read(self):
        """Read encrypted data into cleartext - if not read already."""
        if self.cleartext is None:
            if os.path.exists(self.encrypted_filename):
                self.cleartext = self._decrypt()
            else:
                self.cleartext = ''
        return self.cleartext

    def write(self):
        """Encrypt cleartext and write into destination file file. ."""
        if not self.write_lock:
            raise RuntimeError("write() needs a write lock")
        self._encrypt(self.cleartext)

    def _lock(self):
        self.lockfd = open(self.encrypted_filename,
                           "a+" if self.write_lock else "r+")
        try:
            fcntl.lockf(
                self.lockfd, fcntl.LOCK_EX | fcntl.LOCK_NB |
                (fcntl.LOCK_EX if self.write_lock else fcntl.LOCK_SH))
        except BlockingIOError:
            raise FileLockedError(self.encrypted_filename)

    def _decrypt(self):
        args = [self.gpg()]
        if self.quiet:
            args += ['-q', '--no-tty', '--batch']
        args += ['--decrypt', self.encrypted_filename]
        try:
            result = subprocess.run(
                args,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            raise GPGCallError(args, e.returncode, e.stderr) from e
        else:
            return result.stdout.decode("utf-8")

    def _encrypt(self, data):
        if not self.recipients:
            raise ValueError(
                'Need at least one recipient. Quitting will delete the file.')
        os.rename(self.encrypted_filename, self.encrypted_filename + ".old")
        args = [self.gpg(), '--encrypt']
        for r in self.recipients:
            args.extend(['-r', r.strip()])
        args.extend(['-o', self.encrypted_filename])
        try:
            gpg = subprocess.Popen(args, stdin=subprocess.PIPE)
            gpg.communicate(data.encode("utf-8"))
            if gpg.returncode != 0:
                raise RuntimeError("GPG returned non-zero exit code.")
        except Exception:
            os.rename(self.encrypted_filename + ".old",
                      self.encrypted_filename)
            raise
        else:
            os.unlink(self.encrypted_filename + ".old")


class EncryptedConfigFile(object):
    """Wrap encrypted config files.

    Manages keys based on the data in the configuration. Also allows
    management of additional files with the same keys.

    """

    def __init__(self,
                 encrypted_file,
                 subfile_pattern=None,
                 write_lock=False,
                 quiet=False):
        self.subfile_pattern = subfile_pattern
        self.write_lock = write_lock
        self.quiet = quiet
        self.files = {}

        self.main_file = self.add_file(encrypted_file)

        # Add all existing files to the session
        if self.subfile_pattern:
            for other_filename in glob.iglob(self.subfile_pattern):
                self.add_file(other_filename)

    def add_file(self, filename):
        # Ensure compatibility with pathlib.
        filename = str(filename)
        if filename not in self.files:
            self.files[filename] = f = EncryptedFile(filename, self.write_lock,
                                                     self.quiet)
            f.read()
        return self.files[filename]

    def __enter__(self):
        self.main_file.__enter__()
        # Ensure `self.config`
        self.read()
        return self

    def __exit__(self, _exc_type=None, _exc_value=None, _traceback=None):
        self.main_file.__exit__()
        if not self.get_members():
            os.unlink(self.main_file.encrypted_filename)

    def read(self):
        self.main_file.read()
        if not self.main_file.cleartext:
            self.main_file.cleartext = NEW_FILE_TEMPLATE
        self.config = ConfigUpdater()
        self.config.read_string(self.main_file.cleartext)
        self.set_members(self.get_members())

    def write(self):
        s = io.StringIO()
        self.config.write(s)
        self.main_file.cleartext = s.getvalue()
        for file in self.files.values():
            file.recipients = self.get_members()
            file.write()

    def get_members(self):
        if 'batou' not in self.config:
            self.config.add_section('batou')
        try:
            members = self.config.get("batou", "members").value.split(",")
        except Exception:
            return []
        members = [x.strip() for x in members]
        members = [_f for _f in members if _f]
        members.sort()
        return members

    def set_members(self, members):
        # The whitespace here is exactly what
        # "members = " looks like in the config file so we get
        # proper indentation.
        members = ",\n      ".join(members)
        self.config.set("batou", "members", members)
