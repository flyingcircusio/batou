"""Secure handling of secrets for deployments.

Each deployment environment has an associated set of secrets (ssh keys,
database credentials, etc.). These are stored in encrypted form, in
environments/<name>/secrets.cfg Each deployment environment has its own
secrets file. During the deployment process, the `secrets` feature decrypts the
files and provides the secrets as an additional overlay to top-level
components.

The `secrets edit` program is provided to edit the secrets file in a
convenient fashion::

    ./batou secrets edit myenv

You need to have GPG configured with a default key and need to have all
involved users' keys for an environment to encrypt again.

`secrets edit` launches $EDITOR with the decrypted secrets file
and encrypts it afterwards. If the secrets file did not exist before, a
new one is created.

"""

import pathlib

from batou import DuplicateOverride, SuperfluousSecretsSection

from .encryption import EncryptedConfigFile, iter_other_secrets


def add_secrets_to_environment(environment):
    secrets_file = (
        pathlib.Path("environments") / environment.name / "secrets.cfg"
    )
    if not secrets_file.exists():
        return
    with EncryptedConfigFile(secrets_file) as config_file:
        for section_ in config_file.config.sections():
            if section_ == "batou":
                continue
            elif section_.startswith("host:"):
                hostname = section_.replace("host:", "", 1)
                if hostname not in environment.hosts:
                    raise ValueError(
                        "Secret for unknown host: {}".format(hostname)
                    )
                host = environment.hosts[hostname]
                for key, option in config_file.config.items(section_):
                    if key.startswith("data-"):
                        key = key.replace("data-", "", 1)
                        host.data[key] = option.value
            else:
                component = section_.replace("component:", "")
                if component not in environment.components:
                    environment.exceptions.append(
                        SuperfluousSecretsSection.from_context(component)
                    )
                overrides = environment.overrides.setdefault(component, {})
                for k, v in config_file.config.items(section_):
                    if k in overrides:
                        environment.exceptions.append(
                            DuplicateOverride.from_context(component, k)
                        )
                    else:
                        overrides[k] = v.value
                        environment.secret_data.update(v.value.split())

        # additional_secrets
        for path in iter_other_secrets(environment.name):
            secret_name = path.name.replace("secret-", "", 1)
            with config_file.add_file(path) as other_file:
                other_file.read()
                environment.secret_files[secret_name] = other_file.cleartext
                for line in other_file.cleartext.splitlines():
                    environment.secret_data.update(line.split())
    # Omit too short snippets which might accidentally be part of a file:
    environment.secret_data = {x for x in environment.secret_data if len(x) > 2}
