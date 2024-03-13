import glob
import os
import shutil
import sys
import textwrap

import pytest

from batou.environment import UnknownEnvironmentError

from ..manage import add_user, reencrypt, remove_user, summary


@pytest.mark.parametrize("func", (add_user, remove_user))
def test_manage__1(monkeypatch, func):
    """It raises an exception if called with an unknown environment."""
    monkeypatch.chdir("examples/errors")
    with pytest.raises(UnknownEnvironmentError) as err:
        func("max@example.com", "foo,bar,errors")
    assert "Unknown environment(s): foo, bar" == str(err.value)


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


@pytest.mark.skipif(
    sys.version_info < (3, 7),
    reason="age is available in tests with python 3.7 only",
)
def test_manage__2_age(tmp_path, monkeypatch, capsys):
    """It allows to add/remove_users in an age encrypted environment."""
    shutil.copytree("examples/tutorial-secrets", tmp_path / "tutorial-secrets")
    monkeypatch.chdir(tmp_path / "tutorial-secrets")

    key_name = "https://github.com/ctheune.keys"

    summary()
    out, err = capsys.readouterr()
    assert key_name in out

    remove_user(key_name, "age,age-diffable")
    summary()
    out, err = capsys.readouterr()
    assert key_name not in out

    add_user(key_name, "age,age-diffable")
    summary()
    out, err = capsys.readouterr()
    assert key_name in out


def test_manage__summary__1(capsys, monkeypatch):
    """It prints a summary of the environments, members and secret files."""
    monkeypatch.chdir("examples/errors")
    assert summary() == 0  # exit code
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


def test_manage__summary__3(capsys, monkeypatch):
    """It can decode files where the host is not present."""
    monkeypatch.chdir("examples/errors2")
    assert summary() == 0  # exit code
    out, err = capsys.readouterr()
    expected = "secretserror\n\t members"
    assert expected in out
    assert err == ""


@pytest.mark.skipif(
    sys.version_info < (3, 7),
    reason="age is available in tests with python 3.7 only",
)
def test_manage__reencrypt__1(tmp_path, monkeypatch, capsys):
    """It re-encrypts all files with the current members."""
    shutil.copytree("examples/tutorial-secrets", tmp_path / "tutorial-secrets")

    monkeypatch.chdir(tmp_path / "tutorial-secrets")

    # read files environments/*/secret*
    # and make sure all of them change
    # when we re-encrypt

    old = {}
    for path in glob.glob("environments/*/secret*"):
        with open(path, "rb") as f:
            old[path] = f.read()

    reencrypt("")  # empty string means all environments
    new = {}
    for path in glob.glob("environments/*/secret*"):
        with open(path, "rb") as f:
            new[path] = f.read()

    for path in old:
        assert old[path] != new[path]

    assert set(old) == set(new)
