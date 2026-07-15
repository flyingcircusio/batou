import fcntl
import importlib
import pathlib
import subprocess
import sys
import tempfile
from typing import Callable, Dict, List, Optional, Type

from batou import GPGCallError

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
        try:
            no_change = self.decrypted == content
        except UnicodeDecodeError:
            no_change = False

        if no_change and not reencrypt and content.decode("utf-8") != "":
            return

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

    def _extract_recipients(self) -> Optional[List[str]]:
        """Extract recipient keyids from the encrypted file.

        Returns list of 8-char keyids, or None if extraction fails.
        """
        if not self.path.exists() or self.path.stat().st_size == 0:
            return None

        try:
            result = subprocess.run(
                [
                    self.gpg(),
                    "--list-packets",
                    "--list-options",
                    "show-unusable-subkeys",
                    str(self.path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            output = result.stdout.decode("utf-8")
            recipients = []
            for line in output.splitlines():
                if "keyid" in line:
                    keyid = line.split("keyid")[-1].strip()
                    if keyid and len(keyid) >= 8:
                        # Extract the last 8 characters (keyid is at least 8 chars)
                        recipients.append(keyid[-8:])
            return recipients if recipients else None
        except Exception:
            return None

    def _recipient_to_keyid(self, recipient: str) -> Optional[str]:
        """Convert a recipient (email, keyid, or fingerprint) to 8-char keyid.

        Returns None if recipient cannot be found in keyring.
        """
        recipient = recipient.strip()
        # If it's already a short keyid (8 chars), return it
        if len(recipient) == 8 and recipient.isalnum():
            return recipient
        # If it's a longer keyid or fingerprint, extract the last 8 chars
        if len(recipient) >= 8 and recipient.replace(" ", "").isalnum():
            return recipient[-8:]

        # For email addresses or other formats, look up in GPG keyring
        try:
            result = subprocess.run(
                [self.gpg(), "--list-keys", "--with-colons", recipient],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            output = result.stdout.decode("utf-8")
            for line in output.splitlines():
                # Look for fingerprint field (fpr:) and extract last 8 chars
                if line.startswith("fpr:"):
                    parts = line.split(":")
                    if len(parts) > 9:
                        fpr = parts[9]
                        if fpr and len(fpr) >= 8:
                            keyid = fpr[-8:]
                            # If this keyid matches our recipient (in case it's a short keyid),
                            # return it to handle the case where a short keyid is used in config
                            # but the actual full keyid/fingerprint is in the keyring
                            if keyid == recipient:
                                return keyid
            # Return the last fingerprint's keyid if no exact match found
            for line in reversed(output.splitlines()):
                if line.startswith("fpr:"):
                    parts = line.split(":")
                    if len(parts) > 9:
                        fpr = parts[9]
                        if fpr and len(fpr) >= 8:
                            return fpr[-8:]
        except Exception:
            pass

        return None

    def _write(
        self, content: bytes, recipients: List[str], reencrypt: bool = False
    ):
        if not self.locked:
            raise RuntimeError("File not locked")
        if not self.writeable:
            raise RuntimeError("File not writeable")

        # If not forcing reencrypt, check if content has changed
        if not reencrypt and self.path.exists():
            try:
                # Use the cached decrypted content if available
                old_content = self._decrypted
                if old_content is None:
                    # If not cached, try to decrypt
                    self._decrypted = self.decrypt()
                    old_content = self._decrypted
                if old_content == content:
                    if debug:
                        print(
                            f"Content unchanged, skipping re-encryption of `{self.path}`",
                            file=sys.stderr,
                        )
                    return
            except Exception:
                # If we can't decrypt or compare, proceed with reencryption
                pass

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
