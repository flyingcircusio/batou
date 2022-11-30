import pathlib

import pytest

from batou.secrets.edit import Editor
from batou.secrets.encryption import EncryptedConfigFile

from .test_secrets import encrypted_file


def test_edit(tmpdir):
    with EncryptedConfigFile(str(tmpdir / "asdf"), write_lock=True) as sf:
        editor = Editor(
            "true", environment="none", edit_file=list(sf.files.keys())[0]
        )
        editor.cleartext = "asdf"
        editor.edit()
        assert editor.cleartext == "asdf"


def test_edit_command_loop(tmpdir, capsys):
    with EncryptedConfigFile(str(tmpdir / "asdf"), write_lock=True) as sf:
        editor = Editor(
            "true", environment="none", edit_file=list(sf.files.keys())[0]
        )
        editor.cleartext = "asdf"

        with pytest.raises(ValueError):
            editor.process_cmd("asdf")

        def broken_cmd():
            raise RuntimeError("gpg is broken")

        editor.edit = broken_cmd
        editor.encrypt = broken_cmd

        cmds = ["edit", "asdf", "encrypt", "quit"]

        def _input():
            return cmds.pop(0)

        editor._input = _input
        editor.interact()

    out, err = capsys.readouterr()
    assert err == ""
    assert (
        out
        == """\


An error occurred: gpg is broken

Your changes are still available. You can try:
\tedit       -- opens editor with current data again
\tencrypt    -- tries to encrypt current data again
\tquit       -- quits and loses your changes


An error occurred: gpg is broken

Your changes are still available. You can try:
\tedit       -- opens editor with current data again
\tencrypt    -- tries to encrypt current data again
\tquit       -- quits and loses your changes


An error occurred: unknown command `asdf`

Your changes are still available. You can try:
\tedit       -- opens editor with current data again
\tencrypt    -- tries to encrypt current data again
\tquit       -- quits and loses your changes


An error occurred: gpg is broken

Your changes are still available. You can try:
\tedit       -- opens editor with current data again
\tencrypt    -- tries to encrypt current data again
\tquit       -- quits and loses your changes
"""
    )


def test_edit_file_has_secret_prefix(tmpdir, encrypted_file):
    filename = "asdf123"
    c = EncryptedConfigFile(encrypted_file, write_lock=True)
    with c as _:
        editor = Editor("true", environment="none", edit_file=filename)
        assert editor.edit_file == pathlib.Path("environments") / "none" / (
            f"secret-{filename}"
        )


def test_blank_edit(tmpdir, encrypted_file):
    c = EncryptedConfigFile(encrypted_file, write_lock=True)
    with c as configfile:
        editor = Editor("true", environment="none", edit_file="asdf")
        editor.configfile = configfile
        editor.editing = configfile.add_file(tmpdir / "asdf")
        with editor.editing as f:
            f.read()
            editor.cleartext = editor.original_cleartext = f.cleartext
        editor.edit()
        assert editor.cleartext == ""
        editor.encrypt()
        with open(tmpdir / "asdf", "rb") as f:
            assert f.read() != b""
