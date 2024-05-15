import base64
import errno
import fcntl
import os
import pathlib
import pty
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

from configupdater import ConfigUpdater

from batou import AgeCallError, FileLockedError, GPGCallError
from batou._output import output

debug = False


class EncryptedFile:
    def __init__(self, path: "pathlib.Path", writeable: bool = False):
        self.path = path
        self.writeable = writeable
        self.fd = None
        self.is_new: Optional[bool] = None
        self._decrypted: Optional[bytes] = None

    @property
    def decrypted(self) -> bytes:
        if self.is_new:
            self._decrypted = b""
        if self.path.stat().st_size == 0:
            self._decrypted = b""
        if self._decrypted is None:
            self._decrypted = self.decrypt()
        if self._decrypted is None:
            raise ValueError("No decrypted data available")
        return self._decrypted

    def decrypt(self) -> bytes:
        raise NotImplementedError("decrypt() not implemented")

    @property
    def cleartext(self) -> str:
        return self.decrypted.decode("utf-8")

    @property
    def locked(self) -> bool:
        return self.fd is not None

    def write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        if debug:
            print(
                f"EncryptedFile({self.path}).write({content}, {recipients}, {reencrypt})",
                file=sys.stderr,
            )
        self._decrypted = None
        self._write(content, recipients, reencrypt)
        self._decrypted = content

    def _write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        raise NotImplementedError("_write() not implemented")

    def __enter__(self):
        self._lock()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._unlock()

    def _lock(self):
        if self.locked:
            raise FileLockedError.from_context(self.path)
        if not self.path.exists():
            self.is_new = True
            self.path.touch()
        self.fd = open(self.path, "r+" if self.writeable else "r")
        if debug:
            print(f"Locking `{self.path}`", file=sys.stderr)
        try:
            fcntl.lockf(
                self.fd,
                fcntl.LOCK_NB  # non-blocking
                | (
                    fcntl.LOCK_EX  # exclusive
                    if self.writeable
                    else fcntl.LOCK_SH  # shared
                ),
            )
        except BlockingIOError:
            raise FileLockedError.from_context(self.path)

    def _unlock(self):
        if debug:
            print(f"Unlocking `{self.path}`", file=sys.stderr)
        if self.fd is not None:
            self.fd.close()
            self.fd = None
        if self.is_new:
            self.path.unlink()

    @property
    def exists(self):
        return self.path.exists()

    def delete(self):
        self.path.unlink()


class NoBackingEncryptedFile(EncryptedFile):
    def __init__(self):
        super().__init__(pathlib.Path("/dev/null"))
        self.is_new = True

    def decrypt(self):
        return b""

    @property
    def locked(self):
        return True

    def _lock(self):
        pass

    def _unlock(self):
        pass


class GPGEncryptedFile(EncryptedFile):
    def decrypt(self):
        if not self.locked:
            raise RuntimeError("File not locked")
        args = [self.gpg(), "--decrypt", str(self.path)]

        if debug:
            print(f"Running `{args}`", file=sys.stderr)

        try:
            p = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise GPGCallError.from_context(
                e.cmd, e.returncode, e.stderr
            ) from e
        return p.stdout

    def _write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        if not self.locked:
            raise RuntimeError("File not locked")
        if not self.writeable:
            raise RuntimeError("File not writeable")
        self.path.rename(str(self.path) + ".old")
        old_path = pathlib.Path(str(self.path) + ".old")
        # starting with python 3.8, pathlib.Path's rename() method
        # returns the new path, so we need to store the old path
        args = [self.gpg(), "--encrypt"]
        for recipient in recipients:
            args.extend(["-r", recipient])
        args.extend(["-o", str(self.path)])

        if debug:
            print(f"Running `{args}`", file=sys.stderr)

        try:
            subprocess.run(
                args,
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            old_path.rename(self.path)
            raise GPGCallError.from_context(e.cmd, e.returncode, e.stderr)
        else:
            old_path.unlink()
            self.is_new = False

    _gpg = None
    GPG_BINARY_CANDIDATES = ["gpg", "gpg2"]

    @classmethod
    def gpg(cls):
        if cls._gpg is not None:
            return cls._gpg
        with tempfile.TemporaryFile() as null:
            for gpg in cls.GPG_BINARY_CANDIDATES:
                args = [gpg, "--version"]

                if debug:
                    print(f"Running `{args}`", file=sys.stderr)

                try:
                    subprocess.check_call(args, stdout=null, stderr=null)
                except (subprocess.CalledProcessError, OSError):
                    pass
                else:
                    cls._gpg = gpg
                    return cls._gpg
        raise RuntimeError(
            "Could not find gpg binary."
            " Is GPG installed? I tried looking for: {}".format(
                ", ".join("`{}`".format(x) for x in cls.GPG_BINARY_CANDIDATES)
            )
        )


def expect(fd, expected):
    """
    Expect a certain string on the given file descriptor.
    Returns a tuple of (bool, bytes) where the bool indicates whether the
    expected string was found and the actual output bytes.
    """
    try:
        actual = os.read(fd, len(expected))
    except OSError as e:
        if e.errno == errno.EIO:
            return (False, b"")
        raise
    return (actual == expected, actual)


identities = None


def get_identities():
    global identities
    if identities is None:
        identities = os.environ.get("BATOU_AGE_IDENTITIES")
        identities = (
            [x.strip() for x in identities.split(",")] if identities else []
        )
        if not identities:
            # ssh uses ~/.ssh/id_rsa,
            #  ~/.ssh/id_ecdsa, ~/.ssh/id_ecdsa_sk, ~/.ssh/id_ed25519,
            #  ~/.ssh/id_ed25519_sk and ~/.ssh/id_dsa
            # in that order.
            identities = [
                "~/.ssh/id_rsa",
                "~/.ssh/id_ecdsa",
                "~/.ssh/id_ecdsa_sk",
                "~/.ssh/id_ed25519",
                "~/.ssh/id_ed25519_sk",
                "~/.ssh/id_dsa",
            ]
        # filter on existing files
        identities = [
            os.path.expanduser(x)
            for x in identities
            if os.path.exists(os.path.expanduser(x))
        ]
        if debug:
            print(f"Found identities: {identities}", file=sys.stderr)
    return identities


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
    def decrypt(self):
        if not self.locked:
            raise ValueError("File is not locked")
        identities = get_identities()
        exceptions = []
        for identity in identities:
            with tempfile.NamedTemporaryFile() as temp_file:
                args = [
                    self.age(),
                    "-d",
                    "-i",
                    str(identity),
                    "-o",
                    str(temp_file.name),
                    str(self.path),
                ]

                if debug:
                    print(f"Running `{args}`", file=sys.stderr)

                child_pid, fd = pty.fork()

                IS_CHILD = child_pid == 0

                if IS_CHILD:
                    os.execvp(args[0], args)

                assert not IS_CHILD

                matches, out = expect(
                    fd,
                    b'Enter passphrase for "'
                    + identity.encode("utf-8")
                    + b'": ',
                )

                if matches:
                    passphrase = get_passphrase(identity)
                    os.write(fd, passphrase.encode("utf-8") + b"\n")
                    matches, out = expect(fd, b"\r\r\n")
                    if not matches:
                        exceptions.append(
                            Exception(
                                'Unexpected output from age, expected "\\r\\r\\n": {}'.format(
                                    out
                                )
                            )
                        )
                        continue
                    # also assert, that output is empty from now on
                    buffer = b""
                    while True:
                        try:
                            chunk = os.read(fd, 1024)
                        except OSError as err:  # noqa
                            if err.errno == errno.EIO:
                                # work arond suspected pty "feature", where
                                # reading from the file descriptor
                                # when there is no data raises instead of
                                # returning an empty string, see
                                # https://bugs.python.org/issue5380
                                chunk = None
                        if not chunk:
                            break
                        buffer += chunk
                    if buffer:
                        magic_bytes = b"\x1b[F\x1b[K"
                        if buffer.startswith(magic_bytes):
                            buffer = buffer[len(magic_bytes) :]
                    if buffer:
                        exceptions.append(
                            Exception(
                                "Unexpected output from age: {}".format(buffer)
                            )
                        )
                        continue

                # Wait for the child to exit
                pid, exitcode = os.waitpid(child_pid, 0)

                if exitcode != 0 or pid != child_pid:
                    exceptions.append(
                        AgeCallError.from_context(args, exitcode, out)
                    )
                    continue

                temp_file.seek(0)
                result = temp_file.read()

                if result:
                    return result
        for e in exceptions:
            print(e)
        raise Exception(
            f"Could not decrypt {self.path} with any of the identities {identities}"
        )

    def _write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        if not self.locked:
            raise ValueError("File is not locked")
        if not self.writeable:
            raise ValueError("File is not writeable")
        args = [self.age(), "-e"]
        for recipient in recipients:
            args.extend(["-r", recipient])
        args.extend(["-o", str(self.path)])

        if debug:
            print(f"Running `{args}`", file=sys.stderr)

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

    _age = None
    AGE_BINARY_CANDIDATES = ["age", "rage"]

    @classmethod
    def age(cls):
        if cls._age is not None:
            return cls._age
        with tempfile.TemporaryFile() as null:
            for age in cls.AGE_BINARY_CANDIDATES:
                args = [age, "--version"]
                if debug:
                    print(f"Running `{args}`", file=sys.stderr)
                try:
                    subprocess.check_call(args, stdout=null, stderr=null)
                except (subprocess.CalledProcessError, OSError):
                    pass
                else:
                    cls._age = age
                    return cls._age
        raise RuntimeError(
            "Could not find age binary."
            " Is age installed? I tried looking for: {}".format(
                ", ".join("`{}`".format(x) for x in cls.AGE_BINARY_CANDIDATES)
            )
        )


class DiffableAGEEncryptedFile(EncryptedFile):
    def __init__(self, path: "pathlib.Path", writeable: bool = False):
        super().__init__(path, writeable)
        self._decrypted_content = None
        self._encrypted_content = None

    def decrypt_age_string(self, content: str) -> str:
        # base64 -> tmpfile -> AGEEncryptedFile -> decrypt -> read
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(base64.b64decode(content))
            temp_file.flush()
            with AGEEncryptedFile(pathlib.Path(temp_file.name)) as ef:
                return ef.cleartext

    def encrypt_age_string(self, content: str, recipients: List[str]) -> str:
        # tmpfile -> AGEEncryptedFile -> write plaintext -> read ciphertext -> base64
        with tempfile.NamedTemporaryFile() as temp_file:
            with AGEEncryptedFile(pathlib.Path(temp_file.name), True) as ef:
                ef.write(content.encode("utf-8"), recipients)
            with open(temp_file.name, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

    def decrypt(self):
        # read the entire file, parse as ConfigUpdater

        if not self.locked:
            raise ValueError("File is not locked")

        config_encrypted = ConfigUpdater().read(self.path)
        config = ConfigUpdater().read(self.path)

        # for each section
        for section in config.sections():
            # if section is called batou, skip
            if section == "batou":
                continue
            # for each option
            for option in config[section]:
                # decrypt the value
                decrypted = self.decrypt_age_string(
                    config[section][option].value
                )
                if "\n" in decrypted:
                    # multiline: accounts for indents
                    config[section][option].set_values(
                        decrypted.split("\n"),
                        prepend_newline=False,
                    )
                else:
                    config[section][option].value = decrypted

        # cache the decrypted content
        self._decrypted_content = config
        self._encrypted_content = config_encrypted

        # return the decrypted content as bytes
        return str(config).encode("utf-8")

    def _write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        # parse the content as ConfigUpdater
        config = ConfigUpdater()
        config.read_string(content.decode("utf-8"))

        # for each section
        for section in config.sections():
            # if section is called batou, skip
            if section == "batou":
                continue
            # for each option
            for option in config[section]:
                new_value = config[section][option].value
                assert new_value is not None

                try:
                    old_value = self._decrypted_content[section][option].value
                except Exception:
                    old_value = None

                value_has_changed = new_value != old_value

                if reencrypt or value_has_changed:
                    new_encrypted_value = self.encrypt_age_string(
                        new_value, recipients
                    )
                else:
                    new_encrypted_value = self._encrypted_content[section][
                        option
                    ].value

                config[section][option].value = new_encrypted_value

        # write the config to the file
        with open(self.path, "w") as f:
            f.write(str(config))

        self.is_new = False
