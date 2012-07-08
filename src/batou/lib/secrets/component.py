"""Component to handle secure distribution of secrets"""

from .encryption import EncryptedConfigFile
from .passphrase import use_passphrase
from batou.component import Component
import contextlib
import ConfigParser
import os
import StringIO


class SecretNotFoundError(KeyError):
    pass





class Secrets(Component):
    """Secrets registry.

    Each environment may define a likewise-named cfg file in the
    component source directory that contains sections and options. The
    secrets files are stored encrypted on disk. At configuration time,
    this component asks for a password (unless provided in a password
    file) and exports the decrypted secrets.

    Create/modify a secret file with the `secretsedit` utility.
    Alternatively, you can create secrets files manually with the
    `aespipe` utility::

        aespipe -P passphrase_file <cleartext.cfg >secret.cfg.aes
    """

    passphrase = None

    def remote_bootstrap(self, remote_host):
        with passphrase_file(self.environment, self.service.base) as passphrase:
            remote_host.set(self.root.name, 'passphrase', passphrase)

    def configure(self):
        encrypted_file = u'{}/{}.cfg.aes'.format(
                self.root.defdir, self.environment.name)
        config = ConfigParser.SafeConfigParser()
        with use_passphrase(self.environment, self.service.base,
                self.passphrase) as passphrase:
            with EncryptedConfigFile(encrypted_file, passphrase) as secrets:
                config.readfp(
                    StringIO.StringIO(secrets.read()), encrypted_file)
        self.provide('secrets', config)
