import base64
import errno
import fcntl
import os
import pathlib
import pty
import subprocess
import sys
import tempfile
from typing import Callable, Dict, List, Optional, Type

import pyrage
from configupdater import ConfigUpdater
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from batou import AgeCallError, FileLockedError, GPGCallError
from batou._output import output

debug = False


class EncryptedFile:
    file_ending: Optional[str] = None

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
            raise ValueError(
                f"No decrypted data available for file `{self.path}`"
            )
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
                f"EncryptedFile({self.path}).write({content!r}, {recipients}, {reencrypt})",
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
    file_ending = ".gpg"

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
        paths = [
            os.path.expanduser(x)
            for x in identities
            if os.path.exists(os.path.expanduser(x))
        ]

        if debug:
            print(f"Found identities: {paths}", file=sys.stderr)

        def load(id_path):
            with open(id_path, "rb") as f:
                key_content = f.read()
            try:
                priv_key = serialization.load_ssh_private_key(key_content, None)
            except ValueError:
                passphrase = get_passphrase(id_path).encode("utf-8")
                priv_key = serialization.load_ssh_private_key(
                    key_content,
                    passphrase,
                )

            pkey = priv_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.OpenSSH,
                serialization.NoEncryption(),
            )
            return pyrage.ssh.Identity.from_buffer(pkey)

        identities = []
        for p in paths:
            try:
                x = load(p)
                identities.append(x)
            except Exception as e:
                print(e, file=sys.stderr)
                continue

    return identities


known_passphrases: Dict[str, str] = {}


def get_passphrase(identity: str) -> str:
    """Prompt the user for a passphrase if necessary."""
    if identity in known_passphrases:
        return known_passphrases[identity]

    op = os.environ.get("BATOU_AGE_IDENTITY_PASSPHRASE")

    if op and not op.startswith("op://"):
        passphrase = op
    elif op:
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
    file_ending = ".age"

    def decrypt(self):
        if not self.locked:
            raise ValueError("File is not locked")

        for identity in get_identities():
            try:
                with open(self.path, "rb") as f:
                    encrypted_content = f.read()
                if encrypted_content:
                    result = pyrage.decrypt(encrypted_content, [identity])
                    return result
            except Exception as e:
                print(f"error: {e}")
                continue

    def _write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        if not self.locked:
            raise ValueError("File is not locked")
        if not self.writeable:
            raise ValueError("File is not writeable")

        try:
            recipients = [
                pyrage.ssh.Recipient.from_str(rec) for rec in recipients
            ]
            b = pyrage.encrypt(content, recipients)

            with open(self.path, "wb") as f:
                f.write(b)
            self.is_new = False
        except pyrage.RecipientError:
            self.write_legacy(content, recipients, reencrypt)

    def write_legacy(
        self, content: bytes, recipients: List[str], reencryt: bool = False
    ):
        """
        Fallback to writing secrets with the age binary via subprocesses
        """
        args = ["age", "-e"]
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
            raise AgeCallError.from_context(e.cmd, e.returncode, e.stderr)
        except OSError:
            raise RuntimeError(
                "Could not find age binary. Is age installed? I tried looking for: `age`"
            )
        self.is_new = False


class DiffableAGEEncryptedFile(EncryptedFile):
    file_ending = ".age-diffable"
    _decrypted_content: ConfigUpdater
    _encrypted_content: ConfigUpdater

    def __init__(self, path: "pathlib.Path", writeable: bool = False):
        super().__init__(path, writeable)

    def decrypt_age_string(self, content: str, ident) -> str:
        b = base64.b64decode(content)
        return pyrage.decrypt(b, [ident]).decode("utf-8")

    def encrypt_age_string(
        self, content: str, recipients: List[pyrage.ssh.Recipient]
    ) -> str:
        b = pyrage.encrypt(content.encode("utf-8"), recipients)
        return base64.b64encode(b).decode("utf-8")

    def encrypt_age_string_legacy(
        self, content: str, recipients: List[str]
    ) -> str:
        # tmpfile -> AGEEncryptedFile -> write plaintext -> read ciphertext -> base64
        with tempfile.NamedTemporaryFile() as temp_file:
            with AGEEncryptedFile(pathlib.Path(temp_file.name), True) as ef:
                ef.write_legacy(content.encode("utf-8"), recipients)
            with open(temp_file.name, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

    def decrypt(self):
        # read the entire file, parse as ConfigUpdater

        for ident in get_identities():
            try:
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
                            config[section][option].value, ident
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

            except Exception as e:
                print(f"error: {e}")
                raise e

    def _write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        # parse the content as ConfigUpdater
        config = ConfigUpdater()
        config.read_string(content.decode("utf-8"))

        try:
            recipients = [
                pyrage.ssh.Recipient.from_str(rec) for rec in recipients
            ]
            encrypt_method = self.encrypt_age_string
        except pyrage.RecipientError:
            encrypt_method = self.encrypt_age_string_legacy

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
                    new_encrypted_value = encrypt_method(new_value, recipients)
                else:
                    new_encrypted_value = (
                        self._encrypted_content[section][option].value or ""
                    )

                config[section][option].value = new_encrypted_value

        # write the config to the file
        with open(self.path, "w") as f:
            f.write(str(config))

        self.is_new = False


all_encrypted_file_types: List[Type[EncryptedFile]] = [
    NoBackingEncryptedFile,
    GPGEncryptedFile,
    AGEEncryptedFile,
    DiffableAGEEncryptedFile,
]


def get_encrypted_file(
    path: "pathlib.Path", writeable: bool = False
) -> EncryptedFile:
    """Return the appropriate EncryptedFile object for the given path."""
    for ef in all_encrypted_file_types:
        if ef.file_ending and path.name.endswith(ef.file_ending):
            return ef(path, writeable)
    raise ValueError(f"Unknown encrypted file type for {path}")
