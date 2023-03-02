import fcntl
import os
import pathlib
import pty
import subprocess
import sys
import tempfile
from typing import Dict, List

from configupdater import ConfigUpdater

from batou import AgeCallError, FileLockedError, GPGCallError
from batou._output import output


class EncryptedFile:
    def __init__(self, path: "pathlib.Path", writable: bool = False):
        self.path = path
        self.writable = writable
        self.fd = None
        self.is_new = False

    @property
    def decrypted(self) -> bytes:
        if self.is_new:
            return b""
        if self.path.stat().st_size == 0:
            self.is_new = True
            return b""
        return self._decrypted

    @property
    def _decrypted(self) -> bytes:
        raise NotImplementedError

    @property
    def plaintext(self) -> str:
        return self.decrypted.decode("utf-8")

    @property
    def locked(self) -> bool:
        return self.fd is not None

    def write(self, content: bytes, recipients: List[str]):
        raise NotImplementedError

    def __enter__(self):
        self._lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._unlock()

    def _lock(self):
        if not self.path.exists():
            self.is_new = True
            self.path.touch()
        self.fd = open(self.path, "r+" if self.writable else "r")
        try:
            fcntl.lockf(
                self.fd,
                fcntl.LOCK_NB  # non-blocking
                | (
                    fcntl.LOCK_EX  # exclusive
                    if self.writable
                    else fcntl.LOCK_SH  # shared
                ),
            )
        except BlockingIOError:
            raise FileLockedError.from_context(self.path)

    def _unlock(self):
        if self.fd is not None:
            self.fd.close()
            self.fd = None

    @property
    def exists(self):
        return self.path.exists()


class GPGEncryptedFile(EncryptedFile):
    @property
    def _decrypted(self):
        if not self.locked:
            raise ValueError("File not locked")
        args = ["gpg", "--decrypt", str(self.path)]
        try:
            p = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise GPGCallError.from_context(e.cmd, e.returncode, e.stderr)
        return p.stdout

    def write(self, content: bytes, recipients: List[str]):
        if not self.locked:
            raise ValueError("File not locked")
        if not self.writable:
            raise ValueError("File not writable")
        args = ["gpg", "--encrypt"]
        for recipient in recipients:
            args.extend(["-r", recipient])
        args.extend(["-o", str(self.path)])
        try:
            p = subprocess.run(
                args,
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise GPGCallError.from_context(e.cmd, e.returncode, e.stderr)
        self.is_new = False


def expect(fd, expected):
    """
    Expect a certain string on the given file descriptor.
    Returns a tuple of (bool, bytes) where the bool indicates whether the
    expected string was found and the actual output bytes.
    """
    actual = os.read(fd, len(expected))
    return (actual == expected, actual)


def get_identity():
    identity = os.environ.get("BATOU_AGE_IDENTITY")
    if identity is None:
        raise ValueError("No age identity set in BATOU_AGE_IDENTITY")
    return identity


known_passphrases: Dict[str, str] = {}


def get_passphrase(identity: str) -> str:
    """Prompt the user for a passphrase if necessary."""
    if identity in known_passphrases:
        return known_passphrases[identity]

    op = os.environ.get("BATOU_AGE_IDENTITY_PASSPHRASE")

    if op and not op.startswith("op://"):
        raise ValueError(
            "The environment variable BATOU_AGE_IDENTITY_PASSPHRASE is set, "
            "but it's not an 1password url"
        )

    if op:
        op_process = subprocess.run(
            ["op", "read", op],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        passphrase = op_process.stdout.decode("utf-8").strip()
    else:
        import getpass

        passphrase = getpass.getpass(
            "Enter passphrase for {}: ".format(identity)
        )

    known_passphrases[identity] = passphrase
    return passphrase


class AGEEncryptedFile(EncryptedFile):
    @property
    def _decrypted(self):
        if not self.locked:
            raise ValueError("File is not locked")
        identity = get_identity()
        passphrase = get_passphrase(identity)
        with tempfile.NamedTemporaryFile() as temp_file:
            age_cmd = [
                "age",
                "-d",
                "-i",
                str(identity),
                "-o",
                str(temp_file.name),
                str(self.path),
            ]

            child_pid, fd = pty.fork()

            IS_CHILD = child_pid == 0

            if IS_CHILD:
                os.execvp(age_cmd[0], age_cmd)

            assert not IS_CHILD

            matches, out = expect(
                fd,
                b'Enter passphrase for "' + identity.encode("utf-8") + b'": ',
            )

            if matches:
                os.write(fd, passphrase.encode("utf-8") + b"\n")
                matches, out = expect(fd, b"\r\r\n")
                if not matches:
                    raise Exception(
                        "Unexpected output from age: {}".format(out)
                    )
            else:
                output.annotate(
                    f"No password prompt from age. Output: {out}", debug=True
                )

            # Wait for the child to exit
            pid, exitcode = os.waitpid(child_pid, 0)

            if exitcode != 0 or pid != child_pid:
                raise AgeCallError.from_context(age_cmd, exitcode, out)

            temp_file.seek(0)
            result = temp_file.read()
        # Context manager will close and delete the temp file

        return result

    def write(self, content: bytes, recipients: List[str]):
        if not self.locked:
            raise ValueError("File is not locked")
        if not self.writable:
            raise ValueError("File is not writable")
        args = ["age", "-e"]
        for recipient in recipients:
            args.extend(["-r", recipient])
        args.extend(["-o", str(self.path)])

        try:
            p = subprocess.run(
                args,
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise AgeCallError.from_context(e.cmd, e.returncode, e.stderr)
        self.is_new = False
