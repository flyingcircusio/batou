"""Secure handling of secrets for deployments.

Each deployment environment has an associated set of secrets (ssh keys,
database credentials, etc.). These are stored in encrypted form, in
secrets/<environment>.cfg.pgp Each deployment environment needs its own secrets
file. During the deployment process, the `secrets` feature decrypts the files
and provides the secrets as an additional overlay to top-level components.

The `secretsedit` program is provided to edit the secrets file in a
convenient fashion::

    secretsedit secrets/myenv.cfg.pgp

You need to have gpg configured with a default key and need to have all
involved users' keys for an environment to encrypt again.

`secretsedit` launches $EDITOR with the decrypted secrets file
and encrypts it afterwards. If the secrets file did not exist before, a
new one is created.

"""

from .encryption import EncryptedConfigFile

EncryptedConfigFile     # make pep8 happy
