import fcntl
import io
import os
import pathlib
import subprocess
import tempfile
import urllib.request
from typing import Generator, Optional

from configupdater import ConfigUpdater

from batou import AgeCallError, FileLockedError, GPGCallError

debug = False

# https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
NULL = tempfile.TemporaryFile()

NEW_FILE_TEMPLATE = """\
[batou]
members =
"""


def get_secrets_type(environment_name: str) -> Optional[str]:
    """Return the secrets type for the given environment."""
    environment = pathlib.Path("environments") / environment_name
    if (environment / "secrets.cfg.age").exists():
        if debug:
            print(
                f"""\
get_secrets_type({environment_name}) -> "age" (secrets.cfg.age exists)"""
            )
        return "age"
    elif (environment / "secrets.cfg").exists():
        if debug:
            print(
                f"""\
get_secrets_type({environment_name}) -> "gpg" (secrets.cfg exists)"""
            )
        return "gpg"
    else:
        return "gpg"


def get_secret_config_from_environment_name(
    environment_name: str,
    secrets_type: Optional[str] = None,
) -> pathlib.Path:
    if debug:
        print(
            f"""\
get_secret_config_from_environment_name({environment_name}, {secrets_type})"""
        )
    secrets_type = secrets_type or get_secrets_type(environment_name)
    if secrets_type == "age":
        secrets_file = (
            pathlib.Path("environments") / environment_name / "secrets.cfg.age"
        )
    elif secrets_type == "gpg":
        secrets_file = (
            pathlib.Path("environments") / environment_name / "secrets.cfg"
        )
    else:
        raise ValueError("Unknown secrets type")
    # if not secrets_file.exists():
    #     raise ValueError("No secrets file found for environment")
    # we don't want to raise an error here, because we want to be able to
    # create new secrets files
    return secrets_file


def iter_other_secrets(
    environment_name: str, secrets_type: Optional[str] = None
) -> Generator[pathlib.Path, None, None]:
    """Iterate over the paths to additional encrypted files."""
    environment = pathlib.Path("environments") / environment_name
    secrets_type = secrets_type or get_secrets_type(environment_name)
    for path in environment.iterdir():
        if secrets_type == "age":
            if path.name.startswith("secret-") and path.name.endswith(".age"):
                yield path
        elif secrets_type == "gpg":
            if path.name.startswith("secret-"):
                yield path
        else:
            raise ValueError("Unknown secrets type")


def secret_name_from_path(
    path: pathlib.Path, secrets_type: Optional[str] = None
) -> str:
    """Return the secret name from the path."""
    secrets_type = secrets_type or get_secrets_type(path.parent.name)
    if secrets_type == "age":
        return path.name.replace("secret-", "", 1).replace(".age", "")
    elif secrets_type == "gpg":
        return path.name.replace("secret-", "", 1)
    else:
        raise ValueError("Unknown secrets type")


def get_age_identities():
    """Return a list of age identities."""
    # candidates are ~/.ssh/id_ed25519 and ~/.ssh/id_rsa
    candidates = ["~/.ssh/id_ed25519", "~/.ssh/id_rsa"]
    identities = []
    for candidate in candidates:
        candidate = pathlib.Path(candidate).expanduser()
        if candidate.exists():
            identities.append(candidate)
    return identities


def process_age_recipients(members, environment_path):
    """Process the recipients list."""
    key_meta_file_path = os.path.join(
        environment_path,
        "age_keys.txt",
    )
    key_meta_file_content = ""
    new_members = []
    for key in members:
        key = key.strip()
        if key.startswith("ssh-"):
            # it's a plain ssh public key and we can simply add it
            new_members.append(key)
            key_meta_file_content += f"# plain ssh public key\n{key}\n"
        elif key.startswith("age1"):
            # it's a plain age public key and we can simply add it
            new_members.append(key)
            key_meta_file_content += f"# plain age public key\n{key}\n"
        elif key.startswith("https://") or key.startswith("http://"):
            # it's a url to a key file, so we need to download it
            # and add it to the key meta file
            if key.startswith("http://"):
                print("WARNING: Downloading public keys over http is insecure!")
            key_meta_file_content += f"# ssh key file from {key}\n"
            key_file = urllib.request.urlopen(key)
            key_file_content = key_file.read().decode("utf-8")
            for line in key_file_content.splitlines():
                if line.startswith("ssh-"):
                    new_members.append(line)
                    key_meta_file_content += f"{line}\n"
        else:
            # unknown key type
            print(f"WARNING: Unknown key type for {key}\nWill be ignored!")
    # compare key_meta_file_content and the old one
    # if they differ, we will warn
    if os.path.exists(key_meta_file_path):
        with open(key_meta_file_path, "r") as f:
            old_key_meta_file_content = f.read()
        if old_key_meta_file_content != key_meta_file_content:
            print(
                "WARNING: The key meta file has changed!\n"
                "Please make sure that the new keys are correct!"
            )
    else:
        print(
            "WARNING: The key meta file does not exist!\n"
            "Please make sure that the new keys are correct!"
        )
    # write the new key meta file
    with open(key_meta_file_path, "w") as f:
        f.write(key_meta_file_content)
    return new_members


class EncryptedFile(object):
    """Basic encryption methods - key management handled externally."""

    lockfd = None
    cleartext = None

    is_new = None

    GPG_BINARY_CANDIDATES = ["gpg", "gpg2"]
    AGE_BINARY_CANDIDATES = ["age", "rage"]

    def __init__(
        self,
        encrypted_filename,
        write_lock=False,
        quiet=False,
        secrets_type=None,
    ):
        """Context manager that opens an encrypted file.

        Use the read() and write() methods in the subordinate "with"
        block to manipulate cleartext content. If the cleartext content
        has been replaced, the encrypted file is updated.

        `write_lock` must be set True if a modification of the file is
        intended.
        """
        if debug:
            print(
                f"""\
EncryptedFile.__init__(
    self,
    encrypted_filename={encrypted_filename},
    write_lock={write_lock},
    quiet={quiet},
    secrets_type={secrets_type},
)"""
            )
        # Ensure compatibility with pathlib.
        self.encrypted_filename = str(encrypted_filename)
        self.write_lock = write_lock
        self.quiet = quiet
        self.secrets_type = secrets_type or "gpg"  # fallback to gpg for now
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
                    if debug:
                        print(f'Trying "{gpg} --version"')
                    subprocess.check_call(
                        [gpg, "--version"], stdout=null, stderr=null
                    )
                except (subprocess.CalledProcessError, OSError):
                    pass
                else:
                    return gpg
        raise RuntimeError(
            "Could not find gpg binary."
            " Is GPG installed? I tried looking for: {}".format(
                ", ".join("`{}`".format(x) for x in self.GPG_BINARY_CANDIDATES)
            )
        )

    def age(self):
        with tempfile.TemporaryFile() as null:
            for age in self.AGE_BINARY_CANDIDATES:
                try:
                    if debug:
                        print(f'Trying "{age} --version"')
                    subprocess.check_call(
                        [age, "--version"], stdout=null, stderr=null
                    )
                except (subprocess.CalledProcessError, OSError):
                    pass
                else:
                    return age
        raise RuntimeError(
            "Could not find age binary."
            " Is age installed? I tried looking for: {}".format(
                ", ".join("`{}`".format(x) for x in self.AGE_BINARY_CANDIDATES)
            )
        )

    def read(self):
        """Read encrypted data into cleartext - if not read already."""
        if self.cleartext is None:
            if os.path.exists(self.encrypted_filename):
                self.cleartext = self._decrypt()
            else:
                self.cleartext = ""
        return self.cleartext

    def write(self):
        """Encrypt cleartext and write into destination file file. ."""
        if not self.write_lock:
            raise RuntimeError("write() needs a write lock")
        self.is_new = False
        self._encrypt(self.cleartext)

    def _lock(self):
        if debug:
            print(f"Locking {self.encrypted_filename}")
        # if the file doesn't exist, we set is_new
        if self.is_new is None:
            self.is_new = not os.path.exists(self.encrypted_filename)
        self.lockfd = open(
            self.encrypted_filename, "a+" if self.write_lock else "r+"
        )
        try:
            fcntl.lockf(
                self.lockfd,
                fcntl.LOCK_EX
                | fcntl.LOCK_NB
                | (fcntl.LOCK_EX if self.write_lock else fcntl.LOCK_SH),
            )
        except BlockingIOError:
            raise FileLockedError.from_context(self.encrypted_filename)

    def _decrypt(self):
        if self.secrets_type == "gpg":
            args = [self.gpg()]
            if self.quiet:
                args += ["-q", "--no-tty", "--batch"]
            args += ["--decrypt", self.encrypted_filename]
        elif self.secrets_type == "age":
            args = [self.age()]
            args += ["--decrypt"]
            for identity in get_age_identities():
                args += ["-i", str(identity)]
            args += [self.encrypted_filename]
        try:
            if debug:
                print(f"Decrypting with: {args}")
            result = subprocess.run(
                args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            if self.secrets_type == "gpg":
                raise GPGCallError.from_context(
                    args, e.returncode, e.stderr
                ) from e
            elif self.secrets_type == "age":
                raise AgeCallError.from_context(
                    args, e.returncode, e.stderr
                ) from e
            else:
                raise RuntimeError("Unknown secrets type")
        else:
            return result.stdout.decode("utf-8")

    def _encrypt(self, data):
        if not self.recipients:
            raise ValueError(
                "Need at least one recipient. Quitting will delete the file."
            )
        os.rename(self.encrypted_filename, self.encrypted_filename + ".old")
        if self.secrets_type == "gpg":
            args = [self.gpg(), "--encrypt"]
            for r in self.recipients:
                args.extend(["-r", r.strip()])
            args.extend(["-o", self.encrypted_filename])
        elif self.secrets_type == "age":
            args = [self.age(), "--encrypt"]
            for r in self.recipients:
                args.extend(["-r", r.strip()])
            args.extend(["-o", self.encrypted_filename])
        try:
            if debug:
                print(f"Encrypting with: {args}")
            if self.secrets_type == "gpg":
                gpg = subprocess.Popen(args, stdin=subprocess.PIPE)
                gpg.communicate(data.encode("utf-8"))
                if gpg.returncode != 0:
                    raise RuntimeError("GPG returned non-zero exit code.")
            elif self.secrets_type == "age":
                age = subprocess.Popen(args, stdin=subprocess.PIPE)
                age.communicate(data.encode("utf-8"))
                if age.returncode != 0:
                    raise RuntimeError("age returned non-zero exit code.")
            else:
                raise RuntimeError("Unknown secrets type")
        except Exception:
            os.rename(self.encrypted_filename + ".old", self.encrypted_filename)
            raise
        else:
            os.unlink(self.encrypted_filename + ".old")


class EncryptedConfigFile(object):
    """Wrap encrypted config files.

    Manages keys based on the data in the configuration. Also allows
    management of additional files with the same keys.

    """

    def __init__(
        self,
        encrypted_file,
        add_files_for_env: Optional[str] = None,
        write_lock=False,
        quiet=False,
        secrets_type=None,
    ):
        if debug:
            print(
                f"""\
EncryptedConfigFile.__init__(
    self,
    encrypted_file={encrypted_file},
    add_files_for_env={add_files_for_env},
    write_lock={write_lock},
    quiet={quiet},
    secrets_type={secrets_type})"""
            )
        self.add_files_for_env = add_files_for_env
        self.write_lock = write_lock
        self.quiet = quiet
        self.secrets_type = secrets_type or "gpg"  # fallback to gpg
        self.files = {}

        self.main_file = self.add_file(encrypted_file)

        # Add all existing files to the session
        if self.add_files_for_env:
            for path in iter_other_secrets(
                self.add_files_for_env, self.secrets_type
            ):
                self.add_file(path)

    def add_file(self, filename):
        if debug:
            print(f"add_file: {filename}")
        # Ensure compatibility with pathlib.
        filename = str(filename)
        if filename not in self.files:
            self.files[filename] = f = EncryptedFile(
                filename, self.write_lock, self.quiet, self.secrets_type
            )
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
            if self.secrets_type == "gpg":
                file.recipients = self.get_members()
            elif self.secrets_type == "age":
                file.recipients = process_age_recipients(
                    self.get_members(),
                    os.path.dirname(self.main_file.encrypted_filename),
                )
            else:
                raise RuntimeError("Unknown secrets type")
            file.write()

    def get_members(self):
        if "batou" not in self.config:
            self.config.add_section("batou")
        try:
            members = self.config.get("batou", "members").value.split(",")
        except Exception:
            return []
        members = [x.strip() for x in members]
        members = [_f for _f in members if _f]
        members.sort()
        return members

    def set_members(self, members):
        if debug:
            print(f"set_members: {members}")
        # The whitespace here is exactly what
        # "members = " looks like in the config file so we get
        # proper indentation.
        members = ",\n".join(members)
        # Work around multi-line handling in configupdater
        members = members.split("\n")
        self.config.set("batou", "members", members)
