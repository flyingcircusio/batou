# -*- coding: utf-8 -*-

from batou.lib.file import Content, Mode, Symlink, File, Purge
from batou.lib.file import BinaryFile
from batou.lib.file import ensure_path_nonexistent
from batou.lib.file import Presence, Directory, FileComponent
from mock import Mock, patch
from stat import S_IMODE
import getpass
import os
import pytest
from batou.tests.ellipsis import Ellipsis


def test_ensure_path_nonexistent_removes_normal_file(tmpdir):
    open('asdf', 'w').close()
    assert os.path.exists('asdf')
    ensure_path_nonexistent('asdf')
    assert not os.path.exists('asdf')


def test_ensure_path_nonexistent_removes_normal_symlink(tmpdir):
    os.chdir(str(tmpdir))
    open('target', 'w').close()
    os.symlink('target', 'link')
    assert os.path.exists('link')
    assert os.path.exists('target')

    ensure_path_nonexistent('link')

    assert not os.path.exists('link')
    assert os.path.exists('target')


def test_ensure_path_nonexistent_removes_broken_symlink(tmpdir):
    os.chdir(str(tmpdir))
    os.symlink('target', 'link')
    assert os.path.islink('link')
    assert not os.path.exists('target')
    ensure_path_nonexistent('link')
    assert not os.path.exists('link')
    assert not os.path.exists('target')


def test_ensure_path_nonexistent_removes_directory(tmpdir):
    os.chdir(str(tmpdir))
    os.mkdir('dir')
    assert os.path.exists('dir')
    ensure_path_nonexistent('dir')
    assert not os.path.exists('dir')


def test_ensure_path_does_not_fail_on_nonexisting_path():
    assert not os.path.exists('missing')
    ensure_path_nonexistent('missing')
    assert not os.path.exists('missing')


def test_presence_creates_nonexisting_file(root):
    p = Presence('path')
    root.component += p
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == ''


def test_presence_leaves_existing_file_with_content_intact(root):
    p = Presence('path')
    root.component += p
    with open(p.path, 'w') as f:
        f.write('Hello there!')
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == 'Hello there!'


def test_presence_creates_directories_if_configured(root):
    p = Presence('directory/file', leading=True)
    root.component += p
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == ''


def test_presence_doesnt_create_directories_by_default(root):
    root.component += Presence('directory/file')
    with pytest.raises(IOError):
        root.component.deploy()


def test_presence_removes_conflicting_symlinks(root):
    p = Presence('link')
    root.component += p
    os.symlink('target', p.path)
    assert os.path.islink(p.path)
    with pytest.raises(IOError):
        open(p.path)
    root.component.deploy()
    assert not os.path.islink(p.path)
    with open(p.path) as f:
        assert f.read() == ''


def test_presence_removes_conflicting_directories(root):
    p = Presence('dir')
    root.component += p
    os.mkdir(p.path)
    root.component.deploy()
    assert not os.path.isdir(p.path)
    with open(p.path) as f:
        assert f.read() == ''


def test_directory_creates_directory(root):
    path = 'dir'
    d = Directory(path)
    root.component += d
    assert not os.path.isdir(d.path)
    root.component.deploy()
    assert os.path.isdir(d.path)


def test_directory_creates_leading_directories_if_configured(root):
    path = 'directory/path'
    d = Directory(path, leading=True)
    root.component += d
    root.component.deploy()
    assert os.path.isdir(d.path)


def test_directory_doesnt_create_leading_directories_by_default(root):
    path = 'directory/path'
    root.component += Directory(path)
    with pytest.raises(OSError):
        root.component.deploy()


def test_filecomponent_baseclass_carries_path(root):
    path = 'path'
    p = FileComponent(path)
    root.component += p
    assert p.path.endswith(path)
    assert p.original_path == path


def test_content_passed_by_string(root):
    path = 'path'
    p = Content(path, content='asdf')
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == 'asdf'


def test_content_passed_by_string_template(root):
    path = 'path'
    root.component.foobar = 'asdf'
    p = Content(path,
                content='{{component.foobar}}')
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == 'asdf'


def test_content_with_unicode_requires_encoding(root):
    path = 'path'
    root.component.foobar = 'äsdf'
    p = File(path,
             content='örks {{component.foobar}}',
             encoding='ascii')

    with pytest.raises(UnicodeEncodeError):
        root.component |= p

    p = File(path,
             content='örks {{component.foobar}}',
             encoding='utf-8')
    root.component += p
    root.component.deploy()
    with open(p.path, encoding=p.encoding) as f:
        result = f.read()
        # XXX pytest reporting breaks if this fails. :(
        assert result == 'örks äsdf'


def test_content_passed_by_string_notemplate(root):
    path = 'path'
    root.component.foobar = 'asdf'
    p = Content(path,
                content='{{component.foobar}}',
                is_template=False)
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == '{{component.foobar}}'


def test_content_passed_by_file(root):
    source = 'source'
    with open(source, 'w') as f:
        f.write('content from source file')
    path = 'path'
    p = Content(path, source=source)
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == 'content from source file'


def test_content_passed_by_file_handles_encoding(root):
    source = 'source'
    with open(source, 'w', encoding='latin-1') as f:
        f.write('cöntent from source file')
    path = 'path'
    p = Content(path, source=source, encoding='latin-1')
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path, encoding='latin-1') as f:
        assert f.read() == 'cöntent from source file'


def test_content_passed_by_file_handles_encoding_on_verify(root):
    source = 'source'
    path = 'path'
    p = Content(path, source=source, encoding='latin-1')
    root.component += p
    with open(source, 'w', encoding='latin-1') as f:
        f.write('cöntent from source file')
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path, encoding='latin-1') as f:
        assert f.read() == 'cöntent from source file'


def test_content_passed_by_file_defaults_to_utf8(root):
    source = 'source'
    with open(source, 'w', encoding='utf-8') as f:
        f.write('cöntent from source file')
    path = 'path'
    p = Content(path, source=source)
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path, encoding='utf-8') as f:
        assert f.read() == 'cöntent from source file'


def test_content_passed_by_file_template(root):
    source = 'source'
    with open(source, 'w') as f:
        f.write('{{component.foobar}}')
    path = 'path'
    root.component.foobar = 'asdf'
    p = Content(path, source=source, is_template=True)
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == 'asdf'


def test_content_passed_by_file_template_handles_encoding(root):
    source = 'source'
    with open(source, 'w', encoding='latin-1') as f:
        f.write(
            'cöntent from source file {{component.foo}}')
    path = 'path'
    p = Content(path, source=source, encoding='latin-1')
    root.component.foo = 'foo'
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path, encoding='latin-1') as f:
        assert f.read() == 'cöntent from source file foo'


def test_content_passed_by_file_template_defaults_to_utf8(root):
    source = 'source'
    with open(source, 'w', encoding='utf-8') as f:
        f.write('cöntent from source file {{component.foo}}')
    path = 'path'
    p = Content(path, source=source)
    root.component.foo = 'foo'
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path, encoding='utf-8') as f:
        assert f.read() == 'cöntent from source file foo'


def test_content_passed_by_file_no_template_is_binary(root):
    # This is a regression test for #14944 where UTF 8 in a
    # non-template file caused an accidental implicit encoding to ASCII
    source = 'source'
    with open(source, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
    path = 'path'
    p = Content(path, source=source, is_template=False, encoding=None)
    root.component.foo = 'foo'
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path, 'rb') as f:
        assert f.read() == (
            b'\x89PNG\r\n\x1a\n')


def test_binary_file_component(root):
    # This is a regression test for #14944 where UTF 8 in a
    # non-template file caused an accidental implicit encoding to ASCII
    source = 'source'
    with open(source, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
    path = 'path'
    p = BinaryFile(path, source=source)
    root.component.foo = 'foo'
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path, 'rb') as f:
        assert f.read() == (
            b'\x89PNG\r\n\x1a\n')


def test_content_from_file_as_template_guessed(root):
    path = 'path'
    with open(path, 'w') as f:
        f.write('content from source file {{component.foo}}')
    p = File(path)
    root.component.foo = 'bar'
    root.component += p
    assert p.source == root.defdir + '/path'
    root.component.deploy()
    with open(p.path) as f:
        # Actually, as source and target are the same: nothing happened.
        assert f.read() == 'content from source file bar'


def test_content_source_unclear(root):
    path = 'path'
    p = File(path)
    with pytest.raises(ValueError) as e:
        root.component += p
    assert str(e.value) == (
        "Missing implicit template file {}/path. "
        "Or did you want to create an empty file? "
        "Then use File('path', content='').".format(root.defdir))


def test_content_passed_by_file_using_path_as_default(root):
    path = 'path'
    with open(path, 'w') as f:
        f.write('content from source file')
    p = Content(path)
    root.component += p
    with open(p.path, 'w') as f:
        # Ensure file exists
        pass
    assert p.source == root.defdir + '/path'
    root.component.deploy()
    with open(p.path) as f:
        # Actually, as source and target are the same: nothing happened.
        assert f.read() == 'content from source file'


def test_content_template_with_explicit_context(root):
    path = 'path'
    context = Mock()
    context.foobar = 'asdf'
    p = Content(path,
                content='{{component.foobar}}',
                is_template=True,
                template_context=context)
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == 'asdf'


def test_content_relative_source_path_computed_wrt_definition_dir(root):
    path = 'path'
    source = 'source'
    with open(source, 'w') as f:
        f.write('asdf')
    p = Content(path, source=source)
    root.component += p
    with open(p.path, 'w') as f:
        # The content component assumes there's a file already in place. So
        # we need to create it.
        pass
    root.component.deploy()
    with open(p.path) as f:
        assert f.read() == 'asdf'


def test_content_only_required_changes_touch_file(root):
    path = 'path'
    p = Content(path, content='asdf')
    root.component += p
    # Lets start with an existing file that has the wrong content:
    with open(p.path, 'w') as f:
        f.write('bsdf')
    os.utime(p.path, (0, 0))
    # Modify mtime so we can prove it's been changed.
    root.component.deploy()
    stat = os.stat(p.path)
    assert stat.st_mtime != 0

    os.utime(p.path, (0, 0))
    stat = os.stat(p.path)
    assert stat.st_mtime == 0

    root.component.deploy()
    stat = os.stat(p.path)
    assert stat.st_mtime == 0


def test_content_does_not_allow_both_content_and_source(root):
    path = 'path'
    with pytest.raises(ValueError):
        root.component += Content(path, content='asdf', source='bsdf')


def test_content_large_diff_logged(root):
    from batou import output
    from batou._output import TestBackend

    output.backend = TestBackend()
    path = 'path'
    p = Content(path, content='\n'.join(['asdf']*21))
    p._max_diff = 20
    p._max_diff_lead = 5
    root.component += p
    with open(p.path, 'w') as f:
        f.write('\n'.join(['bsdf']*21))
    root.component.deploy()
    log = os.listdir(p.diff_dir)[0]
    with open(os.path.join(p.diff_dir, log)) as f:
        assert f.read() == '''\
---
+++
@@ -1,21 +1,21 @@
''' + '\n'.join(['-bsdf']*21) + '\n' + '\n'.join(['+asdf']*21) + '\n'

    assert output.backend.output == Ellipsis('''\
host > MyComponent > Content('work/mycomponent/path')
More than 20 lines of diff. Showing first and last 5 lines.
see ... for the full diff.
  path ---
  path +++
  path @@ -1,21 +1,21 @@
  path -bsdf
  path -bsdf
  path ...
  path +asdf
  path +asdf
  path +asdf
  path +asdf
  path +asdf
''')


def test_mode_verifies_for_nonexistent_file(root):
    mode = Mode('asdf', mode=0o000)
    with pytest.raises(AssertionError):
        mode.verify()


def test_mode_ensures_mode_for_files(root):
    path = 'path'
    open('work/mycomponent/' + path, 'w').close()
    mode = Mode(path, mode=0o000)
    root.component += mode
    root.component.deploy()
    assert S_IMODE(os.stat(mode.path).st_mode) == 0o000

    mode.mode = 0o777
    root.component.deploy()
    assert S_IMODE(os.stat(mode.path).st_mode) == 0o777
    assert mode.changed

    root.component.deploy()
    assert not mode.changed


def test_mode_ensures_mode_for_directories(root):
    path = 'path'
    os.makedirs('work/mycomponent/path')
    mode = Mode(path, mode=0o000)
    root.component += mode
    root.component.deploy()
    assert S_IMODE(os.stat(mode.path).st_mode) == 0o000

    mode.mode = 0o777
    root.component.deploy()
    assert S_IMODE(os.stat(mode.path).st_mode) == 0o777
    assert mode.changed

    root.component.deploy()
    assert not mode.changed


@pytest.mark.skipif(not hasattr(os, 'lchmod'), reason='requires lchmod')
def test_mode_ensures_mode_for_symlinks(root):
    # This test is only relevant on platforms that support managing the mode of
    # symlinks.
    link_to = 'link_to'
    open(link_to, 'w').close()
    os.symlink(link_to, 'work/mycomponent/path')
    mode = Mode('path', mode=0o000)
    root.component += mode
    root.component.deploy()
    assert S_IMODE(os.lstat('work/mycomponent/path').st_mode) == 0o000

    mode.mode = 0o777
    root.component.deploy()
    assert S_IMODE(os.lstat('work/mycomponent/path').st_mode) == 0o777
    assert mode.changed

    root.component.deploy()
    assert not mode.changed


@pytest.mark.skipif(hasattr(os, 'lchmod'), reason='requires no lchmod')
def test_mode_does_not_break_on_platforms_without_lchmod(root):
    # This test is only relevant on platforms without lchmod. We basically
    # ensure that deploying the component doesn't break but it's a noop
    # anyway.
    path = 'path'
    link_to = 'link_to'
    open(link_to, 'w').close()
    mode = Mode(path, mode=0o000)
    root.component += mode
    os.symlink(link_to, mode.path)
    root.component.deploy()


def test_symlink_creates_new_link(root):
    link = 'path'
    link_to = 'link_to'
    symlink = Symlink(link, source=link_to)
    root.component += symlink
    root.component.deploy()
    assert os.readlink('work/mycomponent/' + link) == symlink.source


def test_symlink_updates_existing_link(root):
    link = 'path'
    link_to = 'link_to'
    # Create an initial link
    symlink = Symlink(link, source=link_to)
    root.component += symlink
    root.component.deploy()
    # Update link with other target
    link_to2 = 'link_to2'
    symlink.source = link_to2
    root.component.deploy()
    assert os.readlink('work/mycomponent/' + link) == link_to2


def test_file_creates_subcomponent_for_presence(root):
    path = 'path'
    file = File(path, content='')
    assert file.ensure == 'file'
    root.component += file
    assert isinstance(file.sub_components[0], Presence)


def test_file_creates_subcomponent_for_directory(root):
    file = File('dir', ensure='directory')
    root.component += file
    root.component.deploy()
    assert isinstance(file.sub_components[0], Directory)


def test_file_creates_subcomponent_for_symlink(root):
    file = File(
        'link', ensure='symlink', link_to='target')
    root.component += file
    root.component.deploy()
    assert isinstance(file.sub_components[0], Symlink)


def test_file_prohibits_unknown_ensure_parameter(root):
    with pytest.raises(ValueError):
        root.component += File('file', ensure='pipe')


@pytest.mark.slow
def test_directory_copies_all_files(root):
    os.mkdir('source')
    open('source/one', 'w').close()
    open('source/two', 'w').close()
    root.component += Directory('target', source='source')
    root.component.deploy()
    assert sorted(os.listdir('work/mycomponent/target')) == ['one', 'two']


@pytest.mark.slow
def test_directory_last_updated_reflects_file_changes(root):
    os.mkdir('source')
    open('source/one', 'w').close()
    open('source/two', 'w').close()
    d = Directory('target', source='source')
    root.component += d
    root.component.deploy()
    assert (d.last_updated() ==
            os.stat(os.path.join(root.workdir, 'target', 'two')).st_mtime)


@pytest.mark.slow
def test_directory_does_not_copy_excluded_files(root):
    os.mkdir('source')
    open('source/one', 'w').close()
    open('source/two', 'w').close()
    p = Directory(
        'target',
        source='source',
        exclude=('two',))
    root.component += p
    root.component.deploy()
    assert len(os.listdir('work/mycomponent/target')) == 1


@patch('os.chown')
def test_owner_lazy(chown, root):
    with open('asdf', 'w'):
        pass
    file = File('asdf', owner=getpass.getuser())
    root.component += file
    root.component.deploy()
    assert not os.chown.called


@patch('os.chown')
@patch('os.stat')
def test_owner_calls_chown(chown, stat, root):
    os.stat.return_value = Mock()
    os.stat.return_value.st_uid = 0
    os.stat.return_value.st_mode = 0
    file = File('asdf', owner=getpass.getuser(), content='')
    root.component += file
    root.component.deploy()
    assert os.chown.called


def test_owner_is_configurable_when_user_doesnt_exist_yet(root):
    file = File('asdf', owner='foobar', content='')
    # This is a regression test against #12911 and ensures that we can
    # configure a file component's owner even if the owner doesn't exist yet.
    root.component += file


def test_purge_globs_and_deletes_tree(root):
    os.mkdir('work/mycomponent/source')
    open('work/mycomponent/source/one', 'w').close()
    open('work/mycomponent/source/two', 'w').close()
    root.component += Purge('sourc*')
    root.component.deploy()
    assert sorted(os.listdir('work/mycomponent')) == []


def test_purge_globs_and_deletes_files(root):
    os.mkdir('work/mycomponent/source-one')
    open('work/mycomponent/source-two', 'w').close()
    root.component += Purge('sourc*')
    root.component.deploy()
    assert sorted(os.listdir('work/mycomponent')) == []
