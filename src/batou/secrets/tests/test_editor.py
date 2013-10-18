from batou.secrets.edit import Editor
import mock


def test_editor_exits_on_successful_command():
    editor = Editor('vim', mock.Mock())
    editor.edit = mock.Mock()
    editor.encrypt = mock.Mock()
    editor.main()
