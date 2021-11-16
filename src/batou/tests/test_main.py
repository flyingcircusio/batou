import pytest

from ..main import main


def test_main__main__1(tmp_path, monkeypatch, capsys):
    """It enforces running `batou migrate` if not on current version."""
    monkeypatch.setenv('APPENV_BASEDIR', str(tmp_path))
    with pytest.raises(SystemExit):
        main(['deploy', 'test'])
    assert capsys.readouterr().out \
        == 'ERROR: Please run `./batou migrate` first.\n'
