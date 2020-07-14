# -*- coding: utf-8 -*-
from batou.lib.archive import Extract
from pkg_resources import resource_filename
import os
import pytest
import sys
import time


def test_unknown_extension_raises():
    extract = Extract('example.unknown')
    extract.workdir = ''
    with pytest.raises(ValueError):
        extract.configure()


def test_missing_archive_predicts_change(root):
    extract = Extract('example.tar.gz')
    root.component += extract

    extractor = extract.sub_components[0]
    with pytest.raises(AssertionError):
        extractor.verify()


def test_untar_extracts_archive_to_target_directory(root):
    extract = Extract(
        resource_filename(__name__, 'example.tar.gz'),
        target='example')
    root.component += extract
    root.component.deploy()
    assert os.listdir(str(extract.target)) == ['foo']


def test_ignores_ctime_for_directories(root):
    # This is hard to test: ctime can not be changed directly,
    # we thus have to perform a somewhat elaborate dance to align
    # the starts as we wish.
    archive = resource_filename(__name__, 'example.tar.gz')
    extract = Extract(archive, target='example')

    root.component += extract
    root.component.deploy()
    # No assertion raised, nothing to extract
    extract.extractor.verify()

    # Make the archive's ctime newer than the directories, but ensure
    # that the file is current (so only the archives _would_ trigger)
    # if we didn't filter them out properly.
    time.sleep(1.1)
    now = (time.time(), time.time())
    os.utime(archive, now)
    os.utime(str(extract.target) + '/foo/bar/qux', now)

    # No assertion raised, still nothing to extract
    extract.extractor.verify()


def test_untar_can_strip_paths_off_archived_files(root):
    extract = Extract(
        resource_filename(__name__, 'example.tar.gz'),
        target='example', strip=1)
    root.component += extract
    root.component.deploy()
    assert os.listdir(str(extract.target)) == ['bar']


def test_zip_extracts_archive_to_target_directory(root):
    extract = Extract(
        resource_filename(__name__, 'example.zip'),
        target='example')
    root.component += extract
    root.component.deploy()
    assert os.listdir(str(extract.target)) == ['foo']


def test_zip_overwrites_existing_files(root):
    extract = Extract(
        resource_filename(__name__, 'example.zip'),
        target='example')
    root.component += extract

    target = '%s/mycomponent/example/foo/bar' % root.environment.workdir_base
    os.makedirs(target)
    filename = target + '/qux'
    open(filename, 'w').write('foo')
    # Bypass verify (which would do nothing since the just written files
    # are newer than the zip file). XXX The API is a little kludgy here.
    extract.sub_components[0].update()
    assert '' == open(filename).read()


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != 'darwin', reason='only runs on OS X')
def test_dmg_extracts_archive_to_target_directory(root):
    extract = Extract(
        resource_filename(__name__, 'example.dmg'),
        target='example')
    root.component += extract
    root.component.deploy()

    assert sorted(os.listdir(str(extract.target))) == [
        ' ', 'a\u0308sdf.txt', 'example.app']

    # ' ' is a symlink which stays one after copying:
    assert os.path.islink(extract.target + '/ ')
    start_bin = extract.target + '/example.app/MacOS/start.bin'
    with open(start_bin) as start_bin:
        assert start_bin.read() == 'I start the example app! ;)'


def test_dmg_does_not_support_strip(root):
    extract = Extract(
        resource_filename(__name__, 'example.dmg'),
        strip=1,
        target='example')
    with pytest.raises(ValueError) as e:
        root.component += extract
        assert e.value.args[0] == 'Strip is not supported by DMGExtractor'
