import os
import pathlib
import re
import urllib.request
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from configupdater import ConfigUpdater

from batou import (
    DuplicateOverride,
    DuplicateSecretsComponentAttribute,
    SuperfluousSecretsSection,
    UnknownHostSecretsSection,
)
from batou._output import output

from .encryption import (
    AGEEncryptedFile,
    DiffableAGEEncryptedFile,
    EncryptedFile,
    GPGEncryptedFile,
    NoBackingEncryptedFile,
    debug,
)

if TYPE_CHECKING:
    from batou.environment import Environment


class SecretProvider:
    @classmethod
    def from_environment(cls, environment: "Environment") -> "SecretProvider":
        """
        Inspects the environment to determine which secret provider to use.
        Returns an instance of the secret provider.
        """
        environment_path = (
            pathlib.Path(environment.base_dir)
            / "environments"
            / str(environment.name)
        )
        secret_provider_candidates: List[SecretProvider] = []

        # check if environment has a environment.cfg file. If not, it does not
        # exist.

        if not (environment_path / "environment.cfg").exists():
            raise ValueError(f"Environment {environment.name} does not exist.")

        output.annotate(
            f"Looking for secrets for environment {environment.name}.",
            debug=True,
        )

        # There should be one file called "secrets.cfg.<provider>".
        # If there is more than one, we raise an error.

        config_files = list(environment_path.glob("secrets.cfg.*"))
        if len(config_files) == 0:
            output.annotate(
                f"No secrets found for environment {environment.name}.",
                debug=True,
            )
            return NoSecretProvider(environment)
        if len(config_files) > 1:
            raise ValueError(
                f"Multiple secret providers found for environment {environment.name}.",
                f"Candidates: {config_files}. Cannot continue.",
            )

        extension = config_files[0].suffix

        if extension == ".age":
            output.annotate(
                f"Found age secrets for environment {environment.name}.",
                debug=True,
            )
            secret_provider_candidates.append(AGESecretProvider(environment))
        elif extension == ".gpg":
            output.annotate(
                f"Found gpg secrets for environment {environment.name}.",
                debug=True,
            )
            secret_provider_candidates.append(GPGSecretProvider(environment))
        elif extension == ".age-diffable":
            output.annotate(
                f"Found age-diffable secrets for environment {environment.name}.",
                debug=True,
            )
            secret_provider_candidates.append(
                DiffableAGESecretProvider(environment)
            )
        else:
            raise ValueError(
                f"Invalid secret provider {extension}.",
            )

        return secret_provider_candidates[0]

    def __init__(self, environment: "Environment"):
        self.environment = environment

    @property
    def config(self) -> ConfigUpdater:
        raise NotImplementedError(
            "Cannot read encrypted config where no secret provider is configured."
        )

    def read(self) -> "SecretBlob":
        """
        Read the secrets for the environment and return a SecretBlob.
        """
        raise NotImplementedError("read() not implemented.")

    def read_secret_files(self) -> Dict[str, bytes]:
        """
        Read the secret files for the environment and return a dict of
        filename -> content.
        """
        raise NotImplementedError("read_secret_files() not implemented.")

    def inject_secrets(self):
        """
        Inject secrets into the environment.
        """
        output.annotate(
            f"Injecting secrets for environment {self.environment.name}.",
            debug=True,
        )
        secret_blob = self.read()
        for hostname in secret_blob.host_data:
            if hostname not in self.environment.hosts:
                self.environment.exceptions.append(
                    UnknownHostSecretsSection.from_context(hostname)
                )
                continue
            for key, value in secret_blob.host_data[hostname].items():
                self.environment.hosts[hostname].data[key] = value

        for component_name in secret_blob.component_overrides:
            if component_name not in self.environment.components:
                self.environment.exceptions.append(
                    SuperfluousSecretsSection.from_context(component_name)
                )
            overrides = self.environment.overrides.setdefault(
                component_name, {}
            )
            for key, value in secret_blob.component_overrides[
                component_name
            ].items():
                keys_added = set()
                if key in keys_added:
                    self.environment.exceptions.append(
                        DuplicateSecretsComponentAttribute.from_context(
                            component_name, key
                        )
                    )
                elif key in overrides:
                    self.environment.exceptions.append(
                        DuplicateOverride.from_context(component_name, key)
                    )
                else:
                    overrides[key] = value
                    keys_added.add(key)

        self.environment.secret_data.update(secret_blob.secret_data)
        self.environment.secret_files.update(secret_blob.secret_files)

        output.annotate(
            f"Injected secrets for environment {self.environment.name}.",
            debug=True,
        )

    def summary(self):
        """
        Print a summary of the secrets.
        """
        raise NotImplementedError("summary() not implemented.")

    def edit(self, edit_file: Optional[str] = None) -> EncryptedFile:
        """
        Edit the secrets.
        """
        raise NotImplementedError("edit() not implemented.")

    def write_file(self, file: EncryptedFile, content: bytes):
        raise NotImplementedError("write_file() not implemented.")

    def write_config(self, content: bytes, force_reencrypt: bool = False):
        raise NotImplementedError("write_config() not implemented.")

    def write_config_new(self, content: bytes):
        raise NotImplementedError("write_config_new() not implemented.")

    def change_secret_provider(
        self,
        config: ConfigUpdater,
        old_secret_provider: "SecretProvider",
    ):
        new_secret_provider_str = config.get("batou", "secret_provider").value
        if new_secret_provider_str == "age":
            new_secret_provider = AGESecretProvider(self.environment)
        elif new_secret_provider_str == "gpg":
            new_secret_provider = GPGSecretProvider(self.environment)
        elif new_secret_provider_str == "age-diffable":
            new_secret_provider = DiffableAGESecretProvider(self.environment)
        else:
            raise ValueError(
                f"Invalid secret provider {new_secret_provider_str}.",
            )
        output.annotate(
            f"Changing secret provider from {old_secret_provider.secret_provider_str} to {new_secret_provider.secret_provider_str}."
        )
        new_secret_provider.write_config_new(str(config).encode("utf-8"))
        new_secret_provider.write_secret_files(
            old_secret_provider.read_secret_files()
        )
        self.environment.secret_provider = new_secret_provider
        old_secret_provider.purge(new_secret_provider.iter_secret_files())
        output.annotate(
            f"Secret provider changed from {old_secret_provider.secret_provider_str} to {new_secret_provider.secret_provider_str}."
        )

    def purge(self, except_files: Dict[str, EncryptedFile] = {}):
        raise NotImplementedError("purge() not implemented.")

    def _get_recipients(self) -> List[str]:
        raise NotImplementedError("_get_recipients() not implemented.")


class SecretBlob:
    def __init__(
        self,
        host_data: Dict[str, Dict[str, str]],
        component_overrides: Dict[str, Dict[str, str]],
        secret_data: Set[str],
        secret_files: Dict[str, str],
    ):
        """
        Holds the secrets for an environment.
        """
        self.host_data = host_data
        self.component_overrides = component_overrides
        self.secret_data = secret_data
        self.secret_files = secret_files


class NoSecretProvider(SecretProvider):
    secret_provider_str = "none"

    def __init__(self, environment: "Environment"):
        super().__init__(environment)

    def read(self):
        return SecretBlob({}, {}, set(), {})

    def summary(self):
        print("\tNo secrets found.")

    def edit(self, edit_file: Optional[str] = None):
        output.annotate(
            f"Editing secrets for environment {self.environment.name} without secret configuration.",
            debug=True,
        )
        if edit_file is not None:
            raise ValueError(
                "Cannot edit secret files for environment without secret configuration.",
            )
        return NoBackingEncryptedFile()

    def write_config(self, content: bytes, force_reencrypt: bool = False):
        output.annotate(
            f"Writing secrets configuration for environment {self.environment.name} without secret configuration.",
            debug=True,
        )
        self.change_secret_provider(
            ConfigUpdater().read_string(content.decode("utf-8")), self
        )

    def read_secret_files(self) -> Dict[str, bytes]:
        return {}

    def purge(self, except_files: Dict[str, EncryptedFile] = {}):
        pass


class ConfigFileSecretProvider(SecretProvider):
    config_file: EncryptedFile

    @property
    def config(self):
        return ConfigUpdater().read_string(self.config_file.cleartext)

    def read(self):
        host_data = {}  # associate hostnames with their data
        component_overrides = {}  # associate component names with their data
        secret_data = (
            set()
        )  # set of all secret data, used to check for secrets when outputting diffs
        with self.config_file:
            for section in self.config.sections():
                if section == "batou":
                    continue
                elif section.startswith("host:"):
                    hostname = section[len("host:") :]
                    host_data[hostname] = {}
                    for key, option in self.config[section].items():
                        key = key.replace("data-", "", 1)
                        host_data[hostname][key] = option.value
                else:
                    component_name = section.replace("component:", "")
                    component_overrides[component_name] = {}
                    for key, option in self.config[section].items():
                        component_overrides[component_name][key] = option.value
                        if option.value is not None:
                            secret_data.update(option.value.split())

        secret_files = self.read_secret_files()
        secret_files = {k: v.decode("utf-8") for k, v in secret_files.items()}

        for content in secret_files.values():
            secret_data.update(content.splitlines())

        return SecretBlob(
            host_data, component_overrides, secret_data, secret_files
        )

    def iter_secret_files(self, writeable=False) -> Dict[str, EncryptedFile]:
        raise NotImplementedError("iter_secret_files() not implemented.")

    def read_secret_files(self) -> Dict[str, bytes]:
        secret_files = {}
        for filename, file in self.iter_secret_files().items():
            with file:
                secret_files[filename] = file.decrypted
        return secret_files

    def write_secret_files(self, secret_files: Dict[str, bytes]):
        for name, content in secret_files.items():
            with self._get_file(name, writeable=True) as file:
                self.write_file(file, content)

    def purge(self, except_files: Dict[str, EncryptedFile] = {}):
        for name, file in self.iter_secret_files(writeable=True).items():
            if name not in except_files:
                file.delete()
        self.config_file.delete()

    def summary(self):
        print("\t members")
        with self.config_file:
            members = self.config.get("batou", "members")
            if members.value is not None:
                for member in re.split(r"(\n|,)+", members.value):
                    member = member.strip()
                    if member:
                        print(f"\t\t- {member}")
            else:
                print("\t\tUndefined behavior.")
            if not members:
                print("\t\t(none)")
            print("\t secret files")
            # Keys of self.f.files are strings, but self.path is pathlib.Path:
            files = self.read_secret_files().keys()
            files = sorted(files)
            for f in files:
                print("\t\t-", f)
            if not files:
                print("\t\t(none)")
            print()

    def edit(self, edit_file: Optional[str] = None):
        if edit_file is None:
            self.config_file.writeable = True
            return self.config_file
        else:
            return self._get_file(edit_file, writeable=True)

    def _get_file(self, name: str, writeable: bool) -> EncryptedFile:
        raise NotImplementedError("_get_file() not implemented.")

    def write_file(self, file: EncryptedFile, content: bytes):
        recipients = self._get_recipients_for_encryption()
        if not recipients:
            raise ValueError(
                "No recipients found for environment. "
                "Please add a 'batou.members' section to the secrets file."
            )
        file.write(content, recipients)

    def write_config_new(self, content: bytes):
        self.config_file.writeable = True
        with self.config_file:
            self.write_config(content)

    def _get_recipients(self) -> List[str]:
        recipients = self.config.get("batou", "members")

        if recipients.value is None:
            return []
        recipients = re.split(r"(\n|,)+", recipients.value)
        recipients = [r.strip() for r in recipients if r.strip()]
        return recipients


class GPGSecretProvider(ConfigFileSecretProvider):
    secret_provider_str = "gpg"

    def __init__(self, environment: "Environment"):
        super().__init__(environment)
        # load encrypted file
        self.config_file = GPGEncryptedFile(
            pathlib.Path(environment.base_dir)
            / "environments"
            / environment.name
            / "secrets.cfg.gpg"
        )

    def iter_secret_files(self, writeable=False) -> Dict[str, EncryptedFile]:
        environment_path = (
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
        )
        secret_files: Dict[str, EncryptedFile] = {}
        for file in environment_path.glob("secret-*.gpg"):
            file = environment_path / file
            if not file.is_file():
                continue
            name = file.name[len("secret-") : -len(".gpg")]
            secret_files[name] = GPGEncryptedFile(file, writeable)
        return secret_files

    def _get_file(self, name: str, writeable: bool = False) -> EncryptedFile:
        return GPGEncryptedFile(
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
            / f"secret-{name}.gpg",
            writeable,
        )

    def _get_recipients_for_encryption(self) -> List[str]:
        return self._get_recipients()

    def write_config(self, content: bytes, force_reencrypt: bool = False):
        config = ConfigUpdater().read_string(content.decode("utf-8"))
        secret_provider = config.get("batou", "secret_provider", fallback=None)
        if secret_provider is None or secret_provider.value is None:
            config.set("batou", "secret_provider", "gpg")
            print("Setting secret provider to gpg.")
        secret_provider = config.get("batou", "secret_provider")
        if secret_provider.value != "gpg":
            self.change_secret_provider(config, self)
            return
        recipients_opt = config.get("batou", "members")
        if recipients_opt is None or recipients_opt.value is None:
            raise ValueError(
                "Please add a 'batou.members' section to the secrets file."
            )
        recipients = re.split(r"(\n|,)+", recipients_opt.value)
        recipients = [r.strip() for r in recipients if r.strip()]
        if not recipients or len(recipients) == 0 or recipients[0] == "":
            raise ValueError(
                "Please add at least one recipient to the secrets file."
            )
        self.config_file.write(
            str(config).encode("utf-8"),
            recipients,
            reencrypt=force_reencrypt,
        )
        self.write_secret_files(self.read_secret_files())


def process_age_recipients(members, environment_path):
    """Process the recipients list."""
    key_meta_file_path = os.path.join(
        environment_path,
        "age_keys.txt",
    )
    key_meta_file_content = """\
###########################################
# This file is automatically generated by #
# batou. It contains the public keys of   #
# the members of the environment. It is   #
# re-written every time a secrets file is #
# encrypted (after a change).             #
###########################################
"""
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
                raise ValueError(
                    "Downloading public keys over http is insecure!"
                )
            key_meta_file_content += f"# ssh key file from {key}\n"
            if debug:
                print(f"Downloading key file from `{key}`")
            key_file = urllib.request.urlopen(key)
            key_file_content = key_file.read().decode("utf-8")
            remote_keys = sorted(
                [
                    line
                    for line in key_file_content.splitlines()
                    if line.startswith("ssh-")
                ]
            )
            for line in remote_keys:
                new_members.append(line)
                key_meta_file_content += f"{line}\n"
        else:
            # unknown key type
            print(f"WARNING: Unknown key type for {key}\nWill be ignored!")
    # compare key_meta_file_content and the old one
    # if they differ, we will warn
    keys_changed = False
    if os.path.exists(key_meta_file_path):
        with open(key_meta_file_path, "r") as f:
            old_key_meta_file_content = f.read()
        if old_key_meta_file_content != key_meta_file_content:
            keys_changed = True
            print(
                "WARNING: The age encryption public-key metadata file has changed!\n"
                "This means that some secrets are now encrypted with a different set of keys.\n"
                "Please make sure that the new keys are correct and check the file in once you are done."
            )
    else:
        keys_changed = True
        print(
            "WARNING: The age encryption public-key metadata file does not exist!\n"
            "This is not a problem if you are setting up the environment for the first time.\n"
            "Please make sure that the new keys are correct and check the file in once you are done."
        )
    # write the new key meta file
    with open(key_meta_file_path, "w") as f:
        f.write(key_meta_file_content)
    return new_members, keys_changed


class AGESecretProvider(ConfigFileSecretProvider):
    FileFactory = AGEEncryptedFile
    secret_provider_str = "age"

    def __init__(self, environment: "Environment"):
        super().__init__(environment)
        self.config_file = self.FileFactory(
            pathlib.Path(environment.base_dir)
            / "environments"
            / environment.name
            / "secrets.cfg.age"
        )

    def iter_secret_files(self, writeable=False) -> Dict[str, EncryptedFile]:
        environment_path = (
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
        )
        secret_files: Dict[str, EncryptedFile] = {}
        for file in environment_path.glob("secret-*.age"):
            file = environment_path / file
            if not file.is_file():
                continue
            name = file.name[len("secret-") : -len(".age")]
            secret_files[name] = AGEEncryptedFile(file, writeable)
        return secret_files

    def _get_file(self, name: str, writeable: bool = False) -> EncryptedFile:
        return AGEEncryptedFile(
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
            / f"secret-{name}.age",
            writeable,
        )

    def _get_recipients_for_encryption(self) -> List[str]:
        recipients = self._get_recipients()
        return process_age_recipients(
            recipients,
            pathlib.Path(self.environment.base_dir)
            / pathlib.Path("environments")
            / self.environment.name,
        )[0]

    def write_config(self, content: bytes, force_reencrypt: bool = False):
        config = ConfigUpdater().read_string(content.decode("utf-8"))
        secret_provider = config.get("batou", "secret_provider", fallback=None)
        if secret_provider is None or secret_provider.value is None:
            config.set("batou", "secret_provider", self.secret_provider_str)
            print(f"Setting secret provider to {self.secret_provider_str}.")
        secret_provider = config.get("batou", "secret_provider")
        if secret_provider.value != self.secret_provider_str:
            self.change_secret_provider(config, self)
            return
        recipients_opt = config.get("batou", "members")
        if recipients_opt is None or recipients_opt.value is None:
            raise ValueError(
                "Please add a 'batou.members' section to the secrets file."
            )
        recipients = re.split(r"(\n|,)+", recipients_opt.value)
        recipients = [r.strip() for r in recipients if r.strip()]
        if not recipients or len(recipients) == 0 or recipients[0] == "":
            raise ValueError(
                "Please add at least one recipient to the secrets file."
            )
        recipients, keys_changed = process_age_recipients(
            recipients,
            pathlib.Path(self.environment.base_dir)
            / pathlib.Path("environments")
            / self.environment.name,
        )
        self.config_file.write(
            str(config).encode("utf-8"),
            recipients,
            reencrypt=keys_changed or force_reencrypt,
        )
        if keys_changed or force_reencrypt:
            self.write_secret_files(self.read_secret_files())


class DiffableAGESecretProvider(AGESecretProvider):
    FileFactory = DiffableAGEEncryptedFile
    secret_provider_str = "age-diffable"

    def __init__(self, environment: "Environment"):
        super().__init__(environment)
        self.config_file = DiffableAGEEncryptedFile(
            pathlib.Path(environment.base_dir)
            / "environments"
            / environment.name
            / "secrets.cfg.age-diffable"
        )
