"""Securely edit encrypted secret files."""

from .passphrase import PassphraseFile
from .encryption import EncryptedConfigFile
import argparse
import contextlib
import os
import subprocess
import tempfile


class SecretsEditor(object):
    """Utility to invoke an editor over a decrypted secrets file."""

    def __init__(self, encrypted, passphrase_file):
        self.encrypted = encrypted
        self.passphrase_file = passphrase_file

    def __enter__(self):
        return self

    def __exit__(self, *_exc_args):
        pass

    def edit(self, command):
        with self.temporary_cleartext(self.passphrase_file) as cleartext_file:
            subprocess.check_call(
                [command + ' ' + cleartext_file], shell=True)

    @contextlib.contextmanager
    def temporary_cleartext(self, passphrase):
        """Run associated block with a decrypted temporary file."""
        with EncryptedConfigFile(self.encrypted,
                                 passphrase, write_lock=True) as sf:
            cleartext = sf.read()
            with tempfile.NamedTemporaryFile(
                    prefix='edit', suffix='.cfg') as clearfile:
                clearfile.write(cleartext)
                clearfile.flush()
                yield clearfile.name
                with open(clearfile.name, 'r') as new_clearfile:
                    new_cleartext = new_clearfile.read()
                if new_cleartext != cleartext:
                    sf.write(new_cleartext)


def edit():
    """Secrets editor console script.

    The main focus here is to avoid having unencrypted files accidentally
    ending up in the deployment repository.

    """
    parser = argparse.ArgumentParser(
        description=u"""Encrypted secrets file editor utility. Decrypts file,
        invokes the editor, and encrypts the file again. If called with a
        non-existent file name, a new encrypted file is created.""",
        epilog='Relies on aespipe being installed.')
    parser.add_argument('--editor', '-e', metavar='EDITOR',
                        default=os.environ.get('EDITOR', 'vi'),
                        help='Invoke EDITOR to edit (default: $EDITOR or vi)')
    parser.add_argument('filename', metavar='FILE',
                        help='Encrypted secrets file to edit.')
    args = parser.parse_args()
    if os.path.exists(args.filename):
        passphrase_file = PassphraseFile(
            'encrypted file "%s"' % args.filename, double_entry=False)
    else:
        passphrase_file = PassphraseFile(
            'new file "%s"' % args.filename, double_entry=True)
    with passphrase_file as passphrase:
        with SecretsEditor(args.filename, passphrase) as editor:
            editor.edit(args.editor)
