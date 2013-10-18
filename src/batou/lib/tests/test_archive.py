# -*- coding: utf-8 -*-
from batou.lib.archive import DMGExtractor
from pkg_resources import resource_filename
import os
import pytest
import sys


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != 'darwin', reason='only runs on OS X')
def test_dmg_extracts_archive_to_target_directory(root):
    dmg = DMGExtractor(
        resource_filename('batou.lib.tests', 'example.dmg'),
        target='example')
    root.component += dmg
    root.component.deploy()

    assert os.listdir(unicode(dmg.target)) == [
        u' ', u'a\u0308sdf.txt', u'example.app']

    # ' ' is a symlink which stays one after copying:
    assert os.path.islink(dmg.target + '/ ')
    start_bin = dmg.target + '/example.app/MacOS/start.bin'
    with open(start_bin) as start_bin:
        assert start_bin.read() == 'I start the example app! ;)'


def test_dmg_does_not_support_strip(root):
    dmg = DMGExtractor(
        resource_filename('batou.lib.tests', 'example.dmg'),
        strip=1,
        target='example')
    with pytest.raises(ValueError) as e:
        root.component += dmg
        assert e.value.args[0] == 'Strip is not supported by DMGExtractor'
