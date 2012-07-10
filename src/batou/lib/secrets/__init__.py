"""Simplified handling of encrypted secrets files

Each deployment environment has an associated set of secrets (ssh keys,
database credentials, etc.). These are stored in encrypted form, typically as
components/secrets/$ENVIRONMENT.cfg.aes. Each deployment environment needs its
own secrets file. During the deployment process, the `secrets` component
decrypts the secrets files and provides the secrets through the key/value
store.

The passphrase is obtained by

* looking into the file .batou-passphrase or
* asking the user.

The `secretsedit` program is provided to edit the secrets file in a
convenient fashion::

    secretsedit components/secrets/myenv.cfg.aes

asks for a passphrase, launches $EDITOR with the decrypted secrets file
and encrypts it afterwards. If the secrets file did not exist before, a
new one is created.
"""

# Reexport for API
from .component import Secrets  # noqa
