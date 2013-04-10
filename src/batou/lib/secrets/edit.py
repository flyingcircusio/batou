"""Securely edit encrypted secret files."""

from .encryption import EncryptedConfigFile
import argparse
import contextlib
import getpass
import os
import subprocess
import tempfile


class SecretsEditor(object):
    """Utility to invoke an editor over a decrypted secrets file."""

    def __init__(self, encrypted, passphrase):
        self.encrypted = encrypted
        self.passphrase = passphrase

    def __enter__(self):
        return self

    def __exit__(self, *_exc_args):
        pass

    def edit(self, command):
        with self.temporary_cleartext(self.passphrase) as cleartext_file:
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


def get_passphrase(subject):
    if os.path.exists(subject):
        return getpass.getpass('Enter passphrase for encrypted file {}: '.format(subject))

    phrase1 = getpass.getpass('Enter passphrase for new file {}: '.format(subject))
    if len(phrase1) < 20:
        raise RuntimeError(
            'passphrase must be at least 20 characters long')
    phrase2 = getpass.getpass(
        'Enter passphrase for new file {} again: '.format(subject))
    if phrase1 != phrase2:
        raise RuntimeError('passphrases do not match')
    return phrase1


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
    passphrase = get_passphrase(args.filename)
    with SecretsEditor(args.filename, passphrase) as editor:
        editor.edit(args.editor)
