import os
import shutil
import textwrap

import pytest

from ..manage import UnknownEnvironmentError, add_user, remove_user, summary


def test_manage__2(tmp_path, monkeypatch, capsys):
    """It allows to add/remove users."""
    shutil.copytree("examples/errors", tmp_path / "errors")
    monkeypatch.chdir(tmp_path / "errors")

    summary()
    out, err = capsys.readouterr()
    assert "306151601E813A47" in out

    remove_user("306151601E813A47", "errors")
    summary()
    out, err = capsys.readouterr()
    assert "306151601E813A47" not in out

    add_user("306151601E813A47", "errors")
    summary()
    out, err = capsys.readouterr()
    assert "306151601E813A47" in out


def test_manage__summary__1(capsys, monkeypatch):
    """It prints a summary of the environments, members and secret files."""
    monkeypatch.chdir("examples/errors")
    assert summary() is None
    out, err = capsys.readouterr()
    expected = textwrap.dedent(
        """\
        errors
        \t members
        \t\t- 03C7E67FC9FD9364
        \t\t- 306151601E813A47
        \t secret files
        \t\t(none)

    """
    )
    assert out == expected
    assert err == ""


def test_manage__summary__2(capsys, monkeypatch):
    """It prints an error message on decoding problems."""
    monkeypatch.chdir("examples/errors")
    monkeypatch.setitem(os.environ, "GNUPGHOME", "")
    assert summary() == 1  # exit code
    out, err = capsys.readouterr()
    expected = "Exitcode 2 while calling: gpg --decrypt"
    assert out == "errors\n"
    assert err.startswith(expected)
