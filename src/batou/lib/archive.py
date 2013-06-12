from batou.component import Component
from batou.lib.file import Directory
from zipfile import ZipFile
import batou.utils
import itertools
import os
import os.path
import plistlib
import shutil
import zope.cachedescriptors.property


class Extract(Component):

    namevar = 'archive'

    create_target_dir = True
    target = None

    strip = 0

    def configure(self):
        for candidate in [Unzip, Untar, DMGExtractor]:
            if candidate.can_handle(self.archive):
                extractor = candidate(self.archive,
                            target=self.target,
                            create_target_dir=self.create_target_dir,
                            strip=self.strip)
                self += extractor
                break
        else:
            raise ValueError("No handler found for archive '{}'."
                             .format(self.archive))
        self.target = extractor.target


class Extractor(Component):

    namevar = 'archive'

    create_target_dir = True
    suffixes = ()
    strip = 0
    target = None

    @classmethod
    def can_handle(cls, archive):
        return cls.extract_base_name(archive) is not None

    @classmethod
    def extract_base_name(cls, archive):
        for suffix in cls.suffixes:
            if archive.endswith(suffix):
                return archive.rsplit(suffix, 1)[0]

    def configure(self):
        if self.create_target_dir:
            if self.target is None:
                self.target = self.extract_base_name(self.archive)
            if not self.target:
                raise AttributeError(
                    "Target not given and not derivable from archive name "
                    "({}).".format(self.archive))
            self += Directory(self.target, leading=True)
        else:
            self.target = '.'

    def verify(self):
        # Check that all files in the directory are newer than the archive.
        # XXX Might also have a problem regarding archive attribute
        # preservation?
        for filename in self.get_names_from_archive():
            filename = os.path.join(*filename.split(os.path.sep)[self.strip:])
            self.assert_file_is_current(
                os.path.join(self.target, filename),
                [self.archive], key='st_ctime')


class Unzip(Extractor):

    suffixes = ('.zip',)

    def configure(self):
        super(Unzip, self).configure()
        assert self.strip == 0, "Strip is not supported by Unzip"

    def get_names_from_archive(self):
        with ZipFile(self.archive) as f:
            return f.namelist()

    def update(self):
        self.cmd(self.expand(
            'unzip {{component.archive}} -d {{component.target}}'))


class Untar(Extractor):

    suffixes = ('.tar.gz', '.tar', '.tar.bz2', '.tgz')
    exclude = ('._*',)

    def configure(self):
        super(Untar, self).configure()
        self.exclude = ' '.join("--exclude='{}'".format(x)
                                for x in self.exclude)

    def get_names_from_archive(self):
        stdout, stderr = self.cmd(self.expand(
            'tar tf {{component.archive}} {{component.exclude}}'))
        return stdout.splitlines()

    def update(self):
        self.cmd(self.expand(
            'tar xf {{component.archive}} -C {{component.target}} '
            '--strip-components {{component.strip}}'))


class DMGVolume(object):
    """Wrapper to mount an .dgb volume and operate on it."""

    HDIUTIL = '/usr/bin/hdiutil'
    volume_path = None

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.volume_path = self._mount()

    def __del__(self):
        self._unmount()

    def namelist(self):
        for root, dirnames, filenames in os.walk(self.volume_path):
            for name in itertools.chain(dirnames, filenames):
                yield os.path.join(root, name)

    def copy_to(self, target_dir, exclude=None):
        if os.path.exists(target_dir):
            # shutil.copytree insists that the target_dir does not exist
            shutil.rmtree(target_dir)
        shutil.copytree(self.volume_path, target_dir, ignore=exclude)

    def _mount(self):
        """Mount the .dmg file as volume."""
        if not os.path.exists(self.path):
            raise UserWarning('Path %r does not exist.' % self.path)
        volume_path = None
        mount_plist, _ = batou.utils.cmd(
            [self.HDIUTIL, 'mount', '-plist', self.path])
        mount_points = plistlib.readPlistFromString(
            mount_plist)['system-entities']
        if len(mount_points) == 1:
            # maybe there is no content-hint
            volume_path = mount_points[0]['mount-point']
        else:
            for entity in mount_points:
                if entity.get('content-hint') == 'Apple_HFS':
                    volume_path = entity['mount-point']
                    break
        if volume_path is None:
            raise UserWarning('Did not find mounted volume.')
        return volume_path

    def _unmount(self):
        """Unmount and eject the mounted .dmg file."""
        if self.volume_path is not None:
            batou.utils.cmd(
                [self.HDIUTIL, 'eject',
                 self.volume_path.replace(' ', '\ ')])  # XXX: #12527


class DMGExtractor(Extractor):

    suffixes = ('.dmg',)
    exclude = (' ', )  # Typical link to /Applications in App-DMGs

    def configure(self):
        super(DMGExtractor, self).configure()
        assert self.strip == 0, "Strip is not supported by DMGExtractor"

    @zope.cachedescriptors.property.Lazy
    def volume(self):
        return DMGVolume(os.path.join(self.workdir, self.archive))

    def get_names_from_archive(self):
        return self.volume.namelist()

    def update(self):
        exclude = shutil.ignore_patterns(*self.exclude)
        self.volume.copy_to(
            os.path.join(self.workdir, self.target), exclude=exclude)
