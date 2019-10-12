from batou.secrets.edit import Editor
from batou.secrets.encryption import EncryptedConfigFile


def test_edit(tmpdir):
    with EncryptedConfigFile(str(tmpdir / 'asdf'), write_lock=True) as sf:
        editor = Editor('true', sf)
        editor.cleartext = 'asdf'
        editor.edit()
        assert editor.cleartext == 'asdf'
