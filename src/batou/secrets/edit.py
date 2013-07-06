"""Securely edit encrypted secret files."""

from .encryption import EncryptedConfigFile
import argparse
import os
import subprocess
import tempfile


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

    encrypted = args.filename
    command = args.editor

    with EncryptedConfigFile(encrypted, write_lock=True) as sf:
        while True:
            cleartext = sf.read()
            with tempfile.NamedTemporaryFile(
                    prefix='edit', suffix='.cfg') as clearfile:
                clearfile.write(cleartext)
                clearfile.flush()

                subprocess.check_call(
                    [command + ' ' + clearfile.name],
                    shell=True)

                with open(clearfile.name, 'r') as new_clearfile:
                    new_cleartext = new_clearfile.read()

                if new_cleartext == cleartext:
                    break
                try:
                    sf.write(new_cleartext)
                except Exception, e:
                    print "Could not encrypt due to error: {}".format(e)
                    answer = raw_input(
                        "Open editor (type 'edit') or quit and loose changes "
                        "(type 'quit')")
                    if answer == 'quit':
                        break
                else:
                    break
