from batou.lib.file import Content, Mode, Symlink, File
from batou.lib.file import Presence, Directory, FileComponent
from batou.lib.file import ensure_path_nonexistent
from mock import Mock, sentinel
from stat import S_IMODE
import os
import shutil
import tempfile
import time
import unittest


class FileTestBase(object):

    def setUp(self):
        self.base_path = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.base_path)

    def filename(self, *path):
        if not path:
            path = ['path']
        return os.path.join(self.base_path, *path)


class FileRemovalTests(FileTestBase, unittest.TestCase):

    def test_ensure_path_nonexistent_removes_normal_file(self):
        path = self.filename()
        open(path, 'w').close()
        ensure_path_nonexistent(path)
        self.assertFalse(os.path.exists(path))

    def test_ensure_path_nonexistent_removes_normal_symlink(self):
        link_to = self.filename()
        open(link_to, 'w').close()
        link = self.filename('symlink')
        os.symlink(link_to, link)
        ensure_path_nonexistent(link)
        self.assertFalse(os.path.exists(link))
        self.assertTrue(os.path.exists(link_to))

    def test_ensure_path_nonexistent_removes_broken_symlink(self):
        link_to = self.filename()
        link = self.filename('symlink')
        os.symlink(link_to, link)
        ensure_path_nonexistent(link)
        self.assertFalse(os.path.exists(link))
        self.assertFalse(os.path.exists(link_to))

    def test_ensure_path_nonexistent_removes_directory(self):
        directory = self.filename()
        os.mkdir(directory)
        ensure_path_nonexistent(directory)
        self.assertFalse(os.path.exists(directory))

    def test_ensure_path_does_not_fail_on_nonexisting_path(self):
        missing = self.filename()
        self.assertFalse(os.path.exists(missing))
        ensure_path_nonexistent(missing)
        self.assertFalse(os.path.exists(missing))


class FileTests(FileTestBase, unittest.TestCase):

    def deploy(self, component, root=None):
        root = Mock() if root is None else root
        service = Mock()
        service.base = ''
        environment = Mock()
        environment.map.side_effect = lambda x: x
        component.prepare(service, environment, Mock(), root)
        component.deploy()

    def test_presence_creates_nonexisting_file(self):
        path = self.filename()
        p = Presence(path)
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('', f.read())

    def test_presence_leaves_existing_file_with_content_intact(self):
        path = self.filename()
        with open(path, 'w') as f:
            f.write('Hello there!')
        p = Presence(path)
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('Hello there!', f.read())

    def test_presence_creates_directories_if_configured(self):
        path = self.filename('directory', 'file')
        p = Presence(path, leading=True)
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('', f.read())

    def test_presence_doesnt_create_directories_by_default(self):
        path = self.filename('directory', 'file')
        p = Presence(path)
        with self.assertRaises(IOError):
            self.deploy(p)

    def test_presence_removes_conflicting_symlinks(self):
        link_to = self.filename()
        path = self.filename('symlink')
        os.symlink(link_to, path)
        with self.assertRaises(IOError):
            open(path)
        p = Presence(path)
        self.deploy(p)
        self.assertFalse(os.path.islink(path))
        with open(path) as f:
            self.assertEqual('', f.read())

    def test_presence_removes_conflicting_directories(self):
        path = self.filename()
        os.mkdir(path)
        p = Presence(path)
        self.deploy(p)
        self.assertFalse(os.path.isdir(path))
        with open(path) as f:
            self.assertEqual('', f.read())

    def test_directory_creates_directory(self):
        path = self.filename()
        p = Directory(path)
        self.deploy(p)
        self.assertTrue(os.path.isdir(path))

    def test_directory_creates_leading_directories_if_configured(self):
        path = self.filename('directory', 'path')
        p = Directory(path, leading=True)
        self.deploy(p)
        self.assertTrue(os.path.isdir(path))

    def test_directory_doesnt_create_leading_directories_by_default(self):
        path = self.filename('directory', 'path')
        p = Directory(path)
        with self.assertRaises(OSError):
            self.deploy(p)

    def test_filecomponent_baseclass_carries_path(self):
        path = self.filename()
        p = FileComponent(path, leading=sentinel.leading)
        self.deploy(p)
        self.assertEqual(path, p.path)

    def test_content_passed_by_string(self):
        path = self.filename()
        p = Content(path, content='asdf')
        with open(p.path, 'w') as f:
            # The content component assumes there's a file already in place. So
            # we need to create it.
            pass
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('asdf', f.read())

    def test_content_passed_by_string_template(self):
        path = self.filename()
        p = Content(path,
            content='{{component.foobar}}', is_template=True, foobar='asdf')
        with open(p.path, 'w') as f:
            # The content component assumes there's a file already in place. So
            # we need to create it.
            pass
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('asdf', f.read())

    def test_content_passed_by_file(self):
        source = self.filename('source')
        with open(source, 'w') as f:
            f.write('content from source file')
        path = self.filename()
        p = Content(path, source=source)
        with open(p.path, 'w') as f:
            # The content component assumes there's a file already in place. So
            # we need to create it.
            pass
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('content from source file', f.read())

    def test_content_passed_by_file_template(self):
        source = self.filename('source')
        with open(source, 'w') as f:
            f.write('{{component.foobar}}')
        path = self.filename()
        p = Content(path, source=source, is_template=True, foobar='asdf')
        with open(p.path, 'w') as f:
            # The content component assumes there's a file already in place. So
            # we need to create it.
            pass
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('asdf', f.read())

    def test_content_passed_by_file_using_path_as_default(self):
        path = self.filename()
        with open(path, 'w') as f:
            f.write('content from source file')
        p = Content(path)
        self.deploy(p)
        with open(path) as f:
            # Actually, as source and target are the same: nothing happened.
            self.assertEqual('content from source file', f.read())

    def test_content_template_with_explicit_context(self):
        path = self.filename()
        context = Mock()
        context.foobar = 'asdf'
        p = Content(path,
            content='{{component.foobar}}',
            is_template=True,
            template_context=context)
        with open(p.path, 'w') as f:
            # The content component assumes there's a file already in place. So
            # we need to create it.
            pass
        self.deploy(p)
        with open(path) as f:
            self.assertEqual('asdf', f.read())

    def test_content_relative_source_path_computed_wrt_definition_dir(self):
        path = self.filename()
        source = 'source'
        with open(self.filename(source), 'w') as f:
            f.write('asdf')
        p = Content(path, source=source)
        root = Mock()
        root.defdir = self.base_path
        with open(p.path, 'w') as f:
            # The content component assumes there's a file already in place. So
            # we need to create it.
            pass
        self.deploy(p, root=root)
        with open(p.path) as f:
            self.assertEqual('asdf', f.read())

    def test_content_only_required_changes_touch_file(self):
        path = self.filename()
        p = Content(path, content='asdf')
        # Lets start with an existing file that has the wrong content:
        with open(path, 'w') as f:
            f.write('bsdf')
        stat = os.stat(path)
        # Need to sleep a second to ensure that we actually do get different
        # stat results even if the OS has no sub-second resolution.
        time.sleep(1)
        self.deploy(p)
        stat2 = os.stat(path)
        self.assertTrue(stat.st_mtime < stat2.st_mtime)
        # Now, sleeping and running the deployment again will not touch the
        # file.
        time.sleep(1)
        self.deploy(p)
        stat3 = os.stat(path)
        self.assertEqual(stat2.st_mtime, stat3.st_mtime)

    def test_content_does_not_allow_both_content_and_source(self):
        path = self.filename()
        p = Content(path, content='asdf', source='bsdf')
        with self.assertRaises(ValueError):
            self.deploy(p)

    def test_mode_ensures_mode_for_files(self):
        path = self.filename()
        open(path, 'w').close()
        mode = Mode(path, mode=0o000)
        self.deploy(mode)
        self.assertEquals(0o000, S_IMODE(os.stat(path).st_mode))

        mode = Mode(path, mode=0o777)
        self.deploy(mode)
        self.assertEquals(0o777, S_IMODE(os.stat(path).st_mode))
        self.assertTrue(mode.changed)

        self.deploy(mode)
        self.assertFalse(mode.changed)

    def test_mode_ensures_mode_for_directories(self):
        path = self.filename()
        os.mkdir(path)
        mode = Mode(path, mode=0o000)
        self.deploy(mode)
        self.assertEquals(0o000, S_IMODE(os.stat(path).st_mode))

        mode = Mode(path, mode=0o777)
        self.deploy(mode)
        self.assertEquals(0o777, S_IMODE(os.stat(path).st_mode))
        self.assertTrue(mode.changed)

        self.deploy(mode)
        self.assertFalse(mode.changed)

    @unittest.skipUnless(hasattr(os, 'lchmod'),
                         'Only supported on platforms with lchmod')
    def test_mode_ensures_mode_for_symlinks(self):
        # This test is only relevant
        path = self.filename()
        link_to = self.filename('link_to')
        open(link_to, 'w').close()
        os.symlink(link_to, path)
        mode = Mode(path, mode=0o000)
        self.deploy(mode)
        self.assertEquals(0o000, S_IMODE(os.lstat(path).st_mode))

        mode = Mode(path, mode=0o777)
        self.deploy(mode)
        self.assertEquals(0o777, S_IMODE(os.lstat(path).st_mode))
        self.assertTrue(mode.changed)

        self.deploy(mode)
        self.assertFalse(mode.changed)

    @unittest.skipIf(not hasattr(os, 'lchmod'),
                     'Only supported on platforms without lchmod')
    def test_mode_does_not_break_on_platforms_without_lchmod(self):
        # This test is only relevant on platforms without lchmod. We basically
        # ensure that deploying the component doesn't break but it's a noop
        # anyway.
        path = self.filename()
        link_to = self.filename('link_to')
        open(link_to, 'w').close()
        os.symlink(link_to, path)
        mode = Mode(path, mode=0o000)
        self.deploy(mode)

    def test_symlink_creates_new_link(self):
        link = self.filename()
        link_to = self.filename('link-to')
        symlink = Symlink(link, source=link_to)
        self.deploy(symlink)
        self.assertEquals(link_to, os.readlink(link))

    def test_symlink_updates_existing_link(self):
        link = self.filename()
        link_to = self.filename('link-to')
        # Create an initial link
        symlink = Symlink(link, source=link_to)
        self.deploy(symlink)
        # Update link with other target
        link_to2 = self.filename('link-to2')
        symlink = Symlink(link, source=link_to2)
        self.deploy(symlink)
        self.assertEquals(link_to2, os.readlink(link))

    def test_file_creates_subcomponent_for_presence(self):
        path = self.filename()
        file = File(path)
        self.assertEquals('file', file.ensure)
        self.deploy(file)
        self.assertIsInstance(file.sub_components[0], Presence)

    def test_file_creates_subcomponent_for_directory(self):
        path = self.filename()
        file = File(path, ensure='directory')
        self.deploy(file)
        self.assertIsInstance(file.sub_components[0], Directory)

    def test_file_creates_subcomponent_for_symlink(self):
        path = self.filename()
        link_to = self.filename('link-to')
        file = File(path, ensure='symlink', link_to=link_to)
        self.deploy(file)
        self.assertIsInstance(file.sub_components[0], Symlink)

    def test_file_prohibits_unknown_ensure_parameter(self):
        path = self.filename()
        file = File(path, ensure='pipe')
        with self.assertRaises(ValueError):
            self.deploy(file)
