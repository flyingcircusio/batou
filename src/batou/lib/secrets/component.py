"""Component to handle secure distribution of secrets"""

from .encryption import EncryptedConfigFile
from .passphrase import PassphraseFile
from batou.component import Component
import contextlib
import ConfigParser
import os
import StringIO


class SecretNotFoundError(KeyError):
    pass


passphrase_files = {}


@contextlib.contextmanager
def passphrase_file(environment, base):
    """Runs the associated block with a passphrase file.

    The file name of the file containing the passphrase (terminated with
    newline) is passed as a single argument.
    """
    global passphrase_files
    if environment in passphrase_files:
        yield passphrase_files[environment]
        return
    pf = u'%s/.batou-passphrase' % base
    if os.path.exists(pf):
        yield pf
        return
    with PassphraseFile('environment "%s"' % environment.name) as pf:
        yield pf


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

    def configure(self):
        encrypted_file = u'{}/{}.cfg.aes'.format(
                self.root.defdir, self.environment.name)
        config = ConfigParser.SafeConfigParser()
        with passphrase_file(self.environment, self.service.base) as passphrase:
            self.remote_options = [passphrase]
            with EncryptedConfigFile(encrypted_file, passphrase) as secrets:
                config.readfp(
                    StringIO.StringIO(secrets.read()), encrypted_file)
        self.provide('secrets', config)
