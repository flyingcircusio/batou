import argparse
import os
import os.path
import sys
import textwrap
from typing import Optional

import importlib_resources

import batou
import batou.deploy
import batou.migrate
import batou.secrets.edit
import batou.secrets.encryption
import batou.secrets.manage
from batou._output import TerminalBackend, output


def main(args: Optional[list] = None) -> None:
    os.chdir(os.environ["APPENV_BASEDIR"])
    version = (
        importlib_resources.files("batou")
        .joinpath("version.txt")
        .read_text()
        .strip()
    )
    parser = argparse.ArgumentParser(
        description=(
            "batou v{}: multi-(host|component|environment|version|platform)"
            " deployment"
        ).format(version),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.set_defaults(func=parser.print_usage)

    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug mode."
    )

    subparsers = parser.add_subparsers()

    # Deploy
    p = subparsers.add_parser("deploy", help="Deploy an environment.")
    p.set_defaults(func=p.print_usage)

    p.add_argument(
        "-p",
        "--platform",
        default=None,
        help="Alternative platform to choose. Empty for no platform.",
    )
    p.add_argument(
        "-t",
        "--timeout",
        default=None,
        help="Override the environment's timeout setting",
    )
    p.add_argument(
        "-D",
        "--dirty",
        action="store_true",
        help="Allow deploying with dirty working copy or outgoing changes.",
    )
    p.add_argument(
        "-c",
        "--consistency-only",
        action="store_true",
        help="Only perform a deployment model and environment "
        "consistency check. Only connects to a single host. "
        "Does not touch anything.",
    )
    p.add_argument(
        "-P",
        "--predict-only",
        action="store_true",
        help="Only predict what updates would happen. "
        "Do not change anything.",
    )
    p.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help="Defines number of jobs running parallel to deploy. "
        "The default results in a serial deployment "
        "of components. Will override the environment settings "
        "for operational flexibility.",
    )
    p.add_argument(
        "--provision-rebuild",
        action="store_true",
        help="Rebuild provisioned resources from scratch. "
        "DANGER: this is potentially destructive.",
    )
    p.add_argument(
        "environment",
        help="Environment to deploy.",
        type=lambda x: x.replace(".cfg", ""),
    )
    p.set_defaults(func=batou.deploy.main)

    # SECRETS
    secrets = subparsers.add_parser(
        "secrets",
        help=textwrap.dedent(
            """
            Manage encrypted secret files. Relies on age (or GPG) being installed and
            configured correctly. """
        ),
    )
    secrets.set_defaults(func=secrets.print_usage)

    sp = secrets.add_subparsers()

    p = sp.add_parser(
        "edit",
        help=textwrap.dedent(
            """
            Encrypted secrets file editor utility. Decrypts file,
            invokes the editor, and encrypts the file again. If called with a
            non-existent file name, a new encrypted file is created.
        """
        ),
    )
    p.set_defaults(func=p.print_usage)

    p.add_argument(
        "--editor",
        "-e",
        metavar="EDITOR",
        default=os.environ.get("EDITOR", "vi"),
        help="Invoke EDITOR to edit (default: $EDITOR or vi)",
    )
    p.add_argument(
        "environment", help="Environment to edit secrets for.", type=str
    )
    p.add_argument(
        "edit_file",
        nargs="?",
        help="Sub-file to edit. (i.e. secrets/{environment}-{subfile}",
    )
    p.set_defaults(func=batou.secrets.edit.main)

    p = sp.add_parser(
        "summary", help="Give a summary of secret files and who has access."
    )
    p.set_defaults(func=batou.secrets.manage.summary)

    p = sp.add_parser(
        "add", help="Add a user's key to one or more secret files."
    )
    p.set_defaults(func=p.print_usage)
    p.add_argument("keyid", help="The user's key ID or email address")
    p.add_argument(
        "--environments",
        default="",
        help="The environments to update. Update all if not specified.",
    )
    p.set_defaults(func=batou.secrets.manage.add_user)

    p = sp.add_parser(
        "remove", help="Remove a user's key from one or more secret files."
    )
    p.set_defaults(func=p.print_usage)
    p.add_argument("keyid", help="The user's key ID or email address")
    p.add_argument(
        "--environments",
        default="",
        help="The environments to update. Update all if not specified.",
    )
    p.set_defaults(func=batou.secrets.manage.remove_user)

    p = sp.add_parser(
        "reencrypt",
        help="Re-encrypt all secret files with the current members.",
    )
    p.set_defaults(func=p.print_usage)
    p.add_argument(
        "--environments",
        default="",
        help="The environments to update. Update all if not specified.",
    )
    p.set_defaults(func=batou.secrets.manage.reencrypt)

    # migrate
    migrate = subparsers.add_parser(
        "migrate",
        help=textwrap.dedent(
            """
            Migrate the configuration to be compatible with the batou version
            used. Requires to commit the changes afterwards. Might show some
            additional upgrade steps which cannot be performed automatically.
        """
        ),
    )
    migrate.set_defaults(func=migrate.print_usage)
    migrate.add_argument(
        "--bootstrap",
        default=False,
        action="store_true",
        help="Used internally when bootstrapping a new batou project.",
    )
    migrate.set_defaults(func=batou.migrate.main)

    args = parser.parse_args(args)

    # Consume global arguments
    batou.output.enable_debug = args.debug
    batou.secrets.encryption.debug = args.debug
    batou.secrets.manage.debug = args.debug

    # Pass over to function
    if args.func.__name__ == "print_usage":
        args.func()
        sys.exit(1)

    if args.func != batou.migrate.main:
        output.backend = TerminalBackend()
        batou.migrate.assert_up_to_date()

    func_args = dict(args._get_kwargs())
    del func_args["func"]
    del func_args["debug"]
    try:
        return args.func(**func_args)
    except batou.FileLockedError as e:
        # Nicer error reporting for non-deployment commands.
        print(e)
