"""Secure handling of secrets for deployments.

Each deployment environment has an associated set of secrets (ssh keys,
database credentials, etc.). These are stored in encrypted form, in
secrets/<environment>.cfg.pgp Each deployment environment needs its own secrets
file. During the deployment process, the `secrets` feature decrypts the files
and provides the secrets as an additional overlay to top-level components.

The `secretsedit` program is provided to edit the secrets file in a
convenient fashion::

    secretsedit secrets/myenv.cfg

You need to have gpg configured with a default key and need to have all
involved users' keys for an environment to encrypt again.

`secretsedit` launches $EDITOR with the decrypted secrets file
and encrypts it afterwards. If the secrets file did not exist before, a
new one is created.

"""

from batou import SuperfluousSecretsSection
from .encryption import EncryptedConfigFile
import os.path


def add_secrets_to_environment_override(
        environment, enc_file_class=EncryptedConfigFile):
    secrets_file = 'secrets/{}.cfg'.format(environment.name)
    if not os.path.exists(secrets_file):
        return
    with enc_file_class(secrets_file) as f:
        f.read()
        for section_ in f.config.sections():
            if section_ == 'batou':
                continue
            elif section_.startswith('host:'):
                hostname = section_.replace('host:', '', 1)
                if hostname not in environment.hosts:
                    raise ValueError(
                        'Secret for unknown host: {}'.format(hostname))
                host = environment.hosts[hostname]
                for key, value in f.config[section_].items():
                    if key.startswith('data-'):
                        key = key.replace('data-', '', 1)
                        host.data[key] = value
            else:
                component = section_.replace('component:', '')
                if component not in environment.components:
                    environment.exceptions.append(
                        SuperfluousSecretsSection(component))
                o = environment.overrides.setdefault(component, {})
                o.update(f.config.items(section_))
