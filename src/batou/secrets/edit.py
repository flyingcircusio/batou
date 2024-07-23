"""Securely edit encrypted secret files."""

import os
import pathlib
import subprocess
import sys
import tempfile
import traceback
from typing import Optional

from batou.environment import Environment

from .encryption import debug

NEW_FILE_TEMPLATE = """\
[batou]
secret_provider = age
members =
"""


class Editor(object):
    def __init__(
        self,
        editor_cmd,
        environment: Environment,
        edit_file: Optional[str] = None,
    ):
        environment.load_secrets()
        self.editor_cmd = editor_cmd
        self.environment = environment
        self.edit_file = edit_file
        self.file = self.environment.secret_provider.edit(edit_file)

    def main(self):
        with self.file:
            self.original_cleartext = self.file.cleartext
            self.cleartext = self.original_cleartext
            if self.file.is_new:
                self.original_cleartext = None
                if self.edit_file:
                    self.cleartext = ""
                else:
                    self.cleartext = NEW_FILE_TEMPLATE

            self.interact()

    def _input(self):
        return input("> ").strip()

    def interact(self):
        cmd = "edit"
        while cmd != "quit":
            try:
                self.process_cmd(cmd)
            except Exception as e:
                print()
                print()
                print(f"An error occurred: {e}")
                print("Traceback:")
                tb = traceback.format_exc()
                tb_lines = tb.splitlines()
                # if tb is too long, only have first and last 10 lines
                if len(tb_lines) > 20 and not debug:
                    print("\n".join(tb_lines[:10]))
                    print("...")
                    print("\n".join(tb_lines[-10:]))
                else:
                    print(tb)
                print()
                print("Your changes are still available. You can try:")
                print("\tedit       -- opens editor with current data again")
                print("\tencrypt    -- tries to encrypt current data again")
                print("\tquit       -- quits and loses your changes")
                cmd = self._input()
            else:
                break

    def process_cmd(self, cmd):
        if cmd == "edit":
            self.edit()
            self.encrypt()
        elif cmd == "encrypt":
            self.encrypt()
        elif cmd == "":
            raise ValueError("empty command")
        else:
            raise ValueError("unknown command `{}`".format(cmd))

    def encrypt(self):
        if self.cleartext == self.original_cleartext:
            print("No changes from original cleartext. Not updating.")
            return
        if self.edit_file:
            # If we're editing a specific file, we can just overwrite it.
            with self.environment.secret_provider.config_file:
                self.environment.secret_provider.write_file(
                    self.file, self.cleartext.encode("utf-8")
                )
        else:
            self.environment.secret_provider.write_config(
                self.cleartext.encode("utf-8")
            )

    def edit(self):
        filename, _encryption_ext = os.path.splitext(self.file.path.name)
        _, suffix = os.path.splitext(filename)
        with tempfile.NamedTemporaryFile(
            prefix="edit", suffix=suffix, mode="w+", encoding="utf-8"
        ) as clearfile:
            clearfile.write(self.cleartext)
            clearfile.flush()

            args = [self.editor_cmd + " " + clearfile.name]

            if debug:
                print("Running editor with command: {}".format(args))

            subprocess.check_call(args, shell=True)

            with open(clearfile.name, "r") as new_clearfile:
                self.cleartext = new_clearfile.read()


def main(editor, environment, edit_file: Optional[str] = None, **kw):
    """Secrets editor console script.

    The main focus here is to avoid having unencrypted files accidentally
    ending up in the deployment repository.

    """

    try:
        editor = Editor(editor, Environment(environment), edit_file)
        editor.main()
    except Exception as e:
        # only print traceback if we're in debug mode
        if debug:
            traceback.print_exc()
        print(e, file=sys.stderr)
        sys.exit(1)
