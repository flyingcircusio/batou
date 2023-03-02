import os
import pathlib
import urllib.request
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from configupdater import ConfigUpdater

from batou import DuplicateOverride, SuperfluousSecretsSection
from batou._output import output

from .encryption import AGEEncryptedFile, EncryptedFile, GPGEncryptedFile

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
            / environment.name
        )
        secret_provider_candidates: List[SecretProvider] = []

        if (environment_path / "secrets.cfg").exists():
            output.annotate(
                f"Found gpg secrets for environment {environment.name}.",
                debug=True,
            )
            secret_provider_candidates.append(GPGSecretProvider(environment))

        if (environment_path / "secrets.cfg.age").exists():
            output.annotate(
                f"Found age secrets for environment {environment.name}.",
                debug=True,
            )
            secret_provider_candidates.append(AGESecretProvider(environment))

        if len(secret_provider_candidates) > 1:
            raise ValueError(
                f"Multiple secret providers found for environment {environment.name}.",
                f"Candidates: {secret_provider_candidates}. Cannot continue.",
            )

        if len(secret_provider_candidates) == 0:
            output.annotate(
                f"No secrets found for environment {environment.name}.",
                debug=True,
            )
            return NoSecretProvider(environment)

        return secret_provider_candidates[0]

    def __init__(self, environment: "Environment"):
        self.environment = environment

    def read(self) -> "SecretBlob":
        """
        Read the secrets for the environment and return a SecretBlob.
        """
        raise NotImplementedError

    def inject_secrets(self):
        """
        Inject secrets into the environment.
        """
        secret_blob = self.read()
        for hostname in secret_blob.host_data:
            if hostname not in self.environment.hosts:
                raise ValueError(
                    f"Secret for unknown host {hostname}.",
                )
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
                if key in overrides:
                    self.environment.exceptions.append(
                        DuplicateOverride.from_context(component_name, key)
                    )
                else:
                    overrides[key] = value

        self.environment.secret_data.update(secret_blob.secret_data)
        self.environment.secret_files.update(secret_blob.secret_files)

    def summary(self):
        """
        Print a summary of the secrets.
        """
        raise NotImplementedError

    def edit(self, edit_file: Optional[str] = None) -> EncryptedFile:
        """
        Edit the secrets.
        """
        raise NotImplementedError

    def write_file(self, file: EncryptedFile, content: bytes):
        raise NotImplementedError

    def write_config(self, file: EncryptedFile, content: bytes):
        raise NotImplementedError


class SecretBlob:
    def __init__(
        self,
        host_data: Dict[str, Dict[str, str]],
        component_overrides: Dict[str, Dict[str, str]],
        secret_data: Set[str],
        secret_files: Dict[str, str],
    ):
        self.host_data = host_data
        self.component_overrides = component_overrides
        self.secret_data = secret_data
        self.secret_files = secret_files


class NoSecretProvider(SecretProvider):
    def __init__(self, environment: "Environment"):
        super().__init__(environment)

    def read(self):
        return SecretBlob({}, {}, set(), {})

    def summary(self):
        print("\tNo secrets found.")

    def edit(self, edit_file: Optional[str] = None):
        if edit_file is not None:
            raise ValueError(
                "Cannot edit secrets for environment without secrets.",
            )
        return DefaultSecretProvider(self.environment).edit()


class ConfigFileSecretProvider(SecretProvider):
    config_file: EncryptedFile

    @property
    def config(self):
        with self.config_file:
            config = ConfigUpdater().read_string(self.config_file.plaintext)
        return config

    def read(self):
        host_data = {}  # associate hostnames with their data
        component_overrides = {}  # associate component names with their data
        secret_data = (
            set()
        )  # set of all secret data, used to check for secrets when outputting diffs

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

        for content in secret_files.values():
            secret_data.update(content.splitlines())

        return SecretBlob(
            host_data, component_overrides, secret_data, secret_files
        )

    def read_secret_files(self) -> Dict[str, str]:
        raise NotImplementedError

    def summary(self):
        print("\tmembers")
        members = self.config.get("batou", "members")
        if members.value is not None:
            for member in members.value.split(","):
                member = member.strip()
                print(f"\t\t- {member}")
        else:
            print("\t\tUndefined behavior.")
        if not members:
            print("\t\t(none)")

    def edit(self, edit_file: Optional[str] = None):
        if edit_file is None:
            self.config_file.writable = True
            return self.config_file
        else:
            return self._get_file(edit_file, writeable=True)

    def _get_file(self, name: str, writeable: bool) -> EncryptedFile:
        raise NotImplementedError

    def write_file(self, file: EncryptedFile, content: bytes):
        recipients = self._get_recipients()
        if not recipients:
            raise ValueError(
                "No recipients found for environment. "
                "Please add a 'batou.members' section to the secrets file."
            )
        file.write(content, recipients)

    def _get_recipients(self) -> List[str]:
        raise NotImplementedError


class GPGSecretProvider(ConfigFileSecretProvider):
    def __init__(self, environment: "Environment"):
        super().__init__(environment)
        # load encrypted file
        self.config_file = GPGEncryptedFile(
            pathlib.Path(environment.base_dir)
            / "environments"
            / environment.name
            / "secrets.cfg"
        )

    def read_secret_files(self) -> Dict[str, str]:
        environment_path = (
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
        )
        secret_files = {}
        for file in environment_path.glob("secret-*"):
            file = environment_path / file
            if not file.is_file():
                continue
            name = file.name[len("secret-") :]
            with GPGEncryptedFile(file) as encrypted_file:
                secret_files[name] = encrypted_file.plaintext
        return secret_files

    def _get_file(self, name: str, writable: bool = False) -> EncryptedFile:
        return GPGEncryptedFile(
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
            / f"secret-{name}",
            writable,
        )

    def _get_recipients(self) -> List[str]:
        recipients = self.config.get("batou", "members")
        if recipients.value is None:
            return []
        return recipients.value.split(",")


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


class AGESecretProvider(ConfigFileSecretProvider):
    def __init__(self, environment: "Environment"):
        super().__init__(environment)
        self.config_file = AGEEncryptedFile(
            pathlib.Path(environment.base_dir)
            / "environments"
            / environment.name
            / "secrets.cfg.age"
        )

    def read_secret_files(self) -> Dict[str, str]:
        environment_path = (
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
        )
        secret_files = {}
        for file in environment_path.glob("secret-*.age"):
            file = environment_path / file
            if not file.is_file():
                continue
            name = file.name[len("secret-") : -len(".age")]
            with AGEEncryptedFile(file) as encrypted_file:
                secret_files[name] = encrypted_file.plaintext
        return secret_files

    def get_file(self, name: str, writable: bool = False) -> EncryptedFile:
        return AGEEncryptedFile(
            pathlib.Path(self.environment.base_dir)
            / "environments"
            / self.environment.name
            / f"secret-{name}.age",
            writable,
        )

    def _get_recipients(self) -> List[str]:
        recipients = self.config.get("batou", "members")
        if recipients.value is None:
            return []
        recipients = recipients.value.split(",")
        recipients = [r.strip() for r in recipients]
        return process_age_recipients(recipients, self.environment.base_dir)

    def write_config(self, file: EncryptedFile, content: bytes):
        config = ConfigUpdater().read_string(content.decode("utf-8"))
        recipients_opt = config.get("batou", "members")
        if recipients_opt is None or recipients_opt.value is None:
            raise ValueError(
                "Please add a 'batou.members' section to the secrets file."
            )
        recipients = recipients_opt.value.split(",")
        recipients = [r.strip() for r in recipients]
        recipients = process_age_recipients(
            recipients, pathlib.Path("environments") / self.environment.name
        )
        file.write(
            str(config).encode("utf-8"),
            recipients,
        )


DefaultSecretProvider = AGESecretProvider
