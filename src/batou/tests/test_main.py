from unittest import mock

import pytest

from ..main import main


def test_main__main__1(tmp_path, monkeypatch, capsys):
    """It enforces running `batou migrate` if not on current version."""
    monkeypatch.setenv("APPENV_BASEDIR", str(tmp_path))
    with pytest.raises(SystemExit):
        main(["deploy", "test"])
    assert (
        capsys.readouterr().out
        == "ERROR: Please run `./batou migrate` first.\n"
    )


def test_main__main__2(tmp_path, monkeypatch, capsys):
    """It updates to current version on bootstrap."""
    monkeypatch.setenv("APPENV_BASEDIR", str(tmp_path))
    with mock.patch("batou.migrate.main", spec=True) as migrate_main:
        main(["migrate", "--bootstrap"])
    migrate_main.assert_called_with(bootstrap=True)


def test_main__main__3(tmp_path, monkeypatch, capsys):
    """It has useful usage-message if no arguments are given."""
    monkeypatch.setenv("APPENV_BASEDIR", str(tmp_path))
    calling_args = [
        [],
        ["deploy"],
        ["secrets"],
        ["secrets", "edit"],
        ["secrets", "add"],
        ["secrets", "remove"],
    ]
    for args in calling_args:
        joined = " ".join(args)
        with pytest.raises(SystemExit):
            main(args)
        # should contain "usage:"
        # should contain joined as "usage: <joined> other_stuff"
        std = capsys.readouterr()
        output = std.out if std.out else std.err
        assert output.startswith("usage:")
        assert joined in output
