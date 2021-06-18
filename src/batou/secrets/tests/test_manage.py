from ..manage import UnknownEnvironmentError
from ..manage import add_user
from ..manage import remove_user
from ..manage import summary
import pytest
import shutil


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
    assert 'ct@gocept.com' in out

    remove_user('ct@gocept.com', 'errors')
    summary()
    out, err = capsys.readouterr()
    assert 'ct@gocept.com' not in out

    add_user('ct@gocept.com', 'errors')
    summary()
    out, err = capsys.readouterr()
    assert 'ct@gocept.com' in out
