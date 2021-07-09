from ..manage import UnknownEnvironmentError
from ..manage import add_user
from ..manage import remove_user
from ..manage import summary
import os
import pytest
import shutil
import textwrap


@pytest.mark.parametrize('func', (add_user, remove_user))
def test_manage__1(monkeypatch, func):
    """It raises an exception if called with an unknown environment."""
    monkeypatch.chdir('examples/errors')
    with pytest.raises(UnknownEnvironmentError) as err:
        func('max@example.com', 'foo,bar,errors')
    assert 'Unknown environment(s): foo, bar' == str(err.value)


def test_manage__2(tmp_path, monkeypatch, capsys):
    """It allows to add/remove users."""
    shutil.copytree('examples/errors', tmp_path / 'errors')
    monkeypatch.chdir(tmp_path / 'errors')

    summary()
    out, err = capsys.readouterr()
    assert 'cz@flyingcircus.io' in out

    remove_user('cz@flyingcircus.io', 'errors')
    summary()
    out, err = capsys.readouterr()
    assert 'cz@flyingcircus.io' not in out

    add_user('cz@flyingcircus.io', 'errors')
    summary()
    out, err = capsys.readouterr()
    assert 'cz@flyingcircus.io' in out


def test_manage__summary__1(capsys, monkeypatch):
    """It prints a summary of the environments, members and secret files."""
    monkeypatch.chdir('examples/errors')
    assert summary() is None
    out, err = capsys.readouterr()
    expected = textwrap.dedent("""\
        errors
        \t members
        \t\t- ct@gocept.com
        \t\t- cz@flyingcircus.io
        \t secret files
        \t\t(none)

    """)
    assert out == expected
    assert err == ''


def test_manage__summary__2(capsys, monkeypatch):
    """It prints an error message on decoding problems."""
    monkeypatch.chdir('examples/errors')
    monkeypatch.setitem(os.environ, "GNUPGHOME", '')
    assert summary() == 1  # exit code
    out, err = capsys.readouterr()
    expected = ('Exitcode 2 while calling:'
                ' gpg -q --no-tty --batch --decrypt secrets/errors.cfg')
    assert out == ''
    assert err.startswith(expected)
