# -*- coding: utf-8 -*-
from mock import Mock
import os
import shutil
import sys
import tempfile
import unittest


class DMGExtractorTests(unittest.TestCase):
    """Testing ..archive.DMGExtractor."""

    def setUp(self):
        super(DMGExtractorTests, self).setUp()
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        super(DMGExtractorTests, self).tearDown()
        shutil.rmtree(self.tempdir)

    def deploy(self, **kw):
        from ..archive import DMGExtractor
        from pkg_resources import resource_filename
        archive_path = resource_filename('batou.lib.tests', 'example.dmg')

        root = Mock()
        service = Mock()
        service.base = ''
        environment = Mock()
        environment.map.side_effect = lambda x: x

        component = DMGExtractor(archive_path, **kw)
        component.target = self.tempdir

        component.prepare(service, environment, Mock(), root)
        component.deploy()

        return component

    @unittest.skipUnless(sys.platform == 'darwin', 'Requires Mac OS')
    def test_extracts_archive_to_target_directory(self):
        component = self.deploy()
        # Symlink with empty name (usually links to /Applications) is not
        # copied
        self.assertEqual([u'a\u0308sdf.txt', u'example.app'],
                         os.listdir(unicode(component.target)))
        start_bin = os.path.join(
            component.target, 'example.app', 'MacOS', 'start.bin')
        with open(start_bin) as start_bin:
            self.assertEqual('I start the example app! ;)', start_bin.read())

    def test_does_not_support_strip(self):
        with self.assertRaisesRegexp(
                AssertionError, 'Strip is not supported by DMGExtractor'):
            self.deploy(strip=1)
