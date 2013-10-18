from batou.vfs import Developer, Map
from mock import Mock
import os.path


def test_developer_mapping(tmpdir):
    environment = Mock()
    environment.workdir_base = str(tmpdir)
    config = Mock()
    mapping = Developer(environment, config)

    assert mapping.map('/etc') == str(tmpdir / '_' / 'etc')
    assert os.path.exists(str(tmpdir / '_'))
    assert not os.path.exists(str(tmpdir / '_' / 'etc'))

    assert mapping.map('/var') == str(tmpdir / '_' / 'var')
    assert not os.path.exists(str(tmpdir / '_' / 'var'))

    assert mapping.map(str(tmpdir / 'foo')) == str(tmpdir / 'foo')
    assert mapping.map('asdf') == 'asdf'


def test_arbitrary_mapping():
    environment = Mock()
    environment.workdir_base = 'workdir'
    config = {'/a': '/a1',
              # longer paths are preferred matches
              '/a/b': '/a2',
              # non-absolute paths are ignored
              'etc': 'none'}
    mapping = Map(environment, config)

    assert mapping.map('/etc') == '/etc'
    assert mapping.map('/a') == '/a1'
    assert mapping.map('/a/b/c') == '/a2/c'
    assert mapping.map('/a/c') == '/a1/c'
    assert mapping.map('workdir/foo') == 'workdir/foo'
