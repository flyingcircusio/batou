from unittest import mock

import pytest

from ..main import main


def test_main__main__1(tmp_path, monkeypatch, capsys):
    """It enforces running `batou migrate` if not on current version."""
    monkeypatch.setenv('APPENV_BASEDIR', str(tmp_path))
    with pytest.raises(SystemExit):
        main(['deploy', 'test'])
    assert capsys.readouterr().out \
        == 'ERROR: Please run `./batou migrate` first.\n'


def test_main__main__2(tmp_path, monkeypatch, capsys):
    """It updates to current version on bootstrap."""
    monkeypatch.setenv('APPENV_BASEDIR', str(tmp_path))
    with mock.patch('batou.migrate.main', spec=True) as migrate_main:
        main(['migrate', '--bootstrap'])
    migrate_main.assert_called_with(bootstrap=True)
