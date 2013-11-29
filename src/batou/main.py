import argparse
import batou.init
import batou.local
import batou.remote
import batou.secrets.edit
import batou.update
import logging
import os
import os.path
import pkg_resources
import sys


def main():
    os.chdir(os.path.dirname(sys.argv[0]))
    parser = argparse.ArgumentParser(
        description='batou v%s '
        'multi-(host|component|environment|version|platform) deployment'
        % pkg_resources.resource_string(__name__, 'version.txt'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-d', '--debug', action='store_true',
        help='Enable debug mode.')

    subparsers = parser.add_subparsers()

    # INIT
    p = subparsers.add_parser(
        'init',
        help="""\
Initialize batou project in the given directory. If the given directory does
not exist, it will be created.

If no directory is given, the current directory is used.
""")
    p.add_argument('destination')
    p.set_defaults(func=batou.init.main)

    # LOCAL
    p = subparsers.add_parser(
        'local', help=u'Deploy locally.')
    p.add_argument(
        '-p', '--platform', default=None,
        help='Alternative platform to choose. Empty for no platform.')
    p.add_argument(
        '-t', '--timeout', default=None,
        help='Override the environment\'s timeout setting')
    p.add_argument(
        'environment', help='Environment to deploy.',
        nargs='?',
        default='dev',
        type=lambda x: x.replace('.cfg', ''))
    p.add_argument(
        'hostname',
        nargs='?',
        default='localhost',
        help='Host to deploy.')

    p.set_defaults(func=batou.local.main)

    # REMOTE
    p = subparsers.add_parser(
        'remote', help=u'Deploy remotely.')
    p.add_argument(
        'environment', help='Environment to deploy.',
        type=lambda x: x.replace('.cfg', ''))
    p.add_argument(
        '-t', '--timeout', default=None,
        help='Override the environment\'s timeout setting')
    p.add_argument(
        '-D', '--dirty', action='store_true',
        help='Allow deploying with dirty working copy or outgoing changes.')

    p.set_defaults(func=batou.remote.main)

    # SECRETS
    p = subparsers.add_parser(
        'secrets', help="""\
Encrypted secrets file editor utility. Decrypts file,
invokes the editor, and encrypts the file again. If called with a
non-existent file name, a new encrypted file is created.

        Relies on gpg being installed and configured correctly.
""")
    p.add_argument('--editor', '-e', metavar='EDITOR',
                   default=os.environ.get('EDITOR', 'vi'),
                   help='Invoke EDITOR to edit (default: $EDITOR or vi)')
    p.add_argument(
        'environment', help='Environment to edit secrets for.',
        type=lambda x: x.replace('.cfg', ''))
    p.set_defaults(func=batou.secrets.edit.main)

    # UPDATE
    p = subparsers.add_parser(
        'update', help=u'Update the batou version.')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--version', help='Exact version to install.',
        default='')
    group.add_argument(
        '--develop', help='Path to checkout of batou to install in edit mode.',
        default='')
    p.add_argument(
        '--finish', help='(internal)', action='store_true')
    p.set_defaults(func=batou.update.main)

    args = parser.parse_args()

    # Consume global arguments
    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(stream=sys.stdout, level=level, format='%(message)s')

    # Pass over to function
    func_args = dict(args._get_kwargs())
    del func_args['func']
    del func_args['debug']
    args.func(**func_args)
