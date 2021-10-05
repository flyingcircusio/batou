import pytest

from batou.secrets.edit import Editor
from batou.secrets.encryption import EncryptedConfigFile


def test_edit(tmpdir):
    with EncryptedConfigFile(str(tmpdir / "asdf"), write_lock=True) as sf:
        editor = Editor("true", sf)
        editor.cleartext = "asdf"
        editor.edit()
        assert editor.cleartext == "asdf"


def test_edit_command_loop(tmpdir, capsys):
    with EncryptedConfigFile(str(tmpdir / "asdf"), write_lock=True) as sf:
        editor = Editor("true", sf)
        editor.cleartext = "asdf"

        with pytest.raises(ValueError):
            editor.process_cmd('asdf')

        def broken_cmd():
            raise RuntimeError('gpg is broken')

        editor.edit = broken_cmd
        editor.encrypt = broken_cmd

        cmds = ['edit', 'asdf', 'encrypt', 'quit']

        def _input():
            return cmds.pop(0)

        editor._input = _input
        editor.interact()

    out, err = capsys.readouterr()
    assert err == ''
    assert out == """\


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
