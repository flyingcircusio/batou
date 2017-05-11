from batou.component import Component
from batou.lib.file import Directory
from batou.utils import cmd
from zipfile import ZipFile
import itertools
import os
import os.path
import plistlib
import shutil


class Extract(Component):

    namevar = 'archive'

    create_target_dir = True
    target = None

    strip = 0

    def configure(self):
        self.archive = self.map(self.archive)

        for candidate in [Unzip, Untar, DMGExtractor]:
            if candidate.can_handle(self.archive):
                break
        else:
            raise ValueError("No handler found for archive '{}'."
                             .format(self.archive))
        extractor = candidate(
            self.archive,
            target=self.target,
            create_target_dir=self.create_target_dir,
            strip=self.strip)
        self += extractor
        self.target = extractor.target

    @property
    def namevar_for_breadcrumb(self):
        return os.path.basename(self.archive)


class Extractor(Component):

    namevar = 'archive'

    _supports_strip = False

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
        if self.strip and not self._supports_strip:
            raise ValueError("Strip is not supported by {}".format(
                self.__class__.__name__))
        if self.create_target_dir:
            if self.target is None:
                self.target = self.extract_base_name(self.archive)
            if not self.target:
                raise AttributeError(
                    "Target not given and not derivable from archive name "
                    "({}).".format(self.archive))
            d = Directory(self.target, leading=True)
            self += d
            self.target = d.path
        else:
            self.target = self.map('.')

    def verify(self):
        # Check that all files in the directory are newer than the archive.
        # XXX Might also have a problem regarding archive attribute
        # preservation?
        for filename in self.get_names_from_archive():
            filename = os.path.join(*filename.split(os.path.sep)[self.strip:])
            self.assert_file_is_current(
                os.path.join(self.target, filename),
                [self.archive], key='st_ctime')

    @property
    def namevar_for_breadcrumb(self):
        return os.path.basename(self.archive)


class Unzip(Extractor):

    suffixes = ('.zip',)

    def get_names_from_archive(self):
        with ZipFile(self.archive) as f:
            return f.namelist()

    def update(self):
        self.cmd(self.expand(
            'unzip -o {{component.archive}} -d {{component.target}}'))


class Untar(Extractor):

    suffixes = ('.tar.gz', '.tar', '.tar.bz2', '.tgz', 'tar.xz')
    exclude = ('._*',)
    _supports_strip = True

    def configure(self):
        super(Untar, self).configure()
        self.exclude = ' '.join("--exclude='{}'".format(x)
                                for x in self.exclude)

    def get_names_from_archive(self):
        # Note, this does not work combined with strip ... :/
        stdout, stderr = self.cmd(
            'tar tf {{component.archive}} {{component.exclude}}')
        return stdout.splitlines()

    def update(self):
        self.cmd(
            'tar xf {{component.archive}} -C {{component.target}} '
            '--strip-components {{component.strip}}')


class DMGVolume(object):
    """Wrapper to mount a .dmg volume and operate on it."""

    HDIUTIL = '/usr/bin/hdiutil'
    volume_path = None

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.volume_path = self._mount()

    def namelist(self):
        for root, dirnames, filenames in os.walk(self.volume_path):
            for name in itertools.chain(dirnames, filenames):
                yield os.path.join(root, name)

    def copy_to(self, target_dir):
        if os.path.exists(target_dir):
            # shutil.copytree insists that the target_dir does not exist
            shutil.rmtree(target_dir)
        shutil.copytree(self.volume_path, target_dir, symlinks=True)

    def _mount(self):
        """Mount the .dmg file as volume."""
        if not os.path.exists(self.path):
            raise UserWarning('Path %r does not exist.' % self.path)
        volume_path = None
        mount_plist, _ = cmd(
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
            cmd([self.HDIUTIL, 'eject', self.volume_path])


class DMGExtractor(Extractor):

    suffixes = ('.dmg',)

    def __enter__(self):
        self.volume = DMGVolume(self.archive)

    def __exit__(self, type, value, tb):
        self.volume._unmount()

    def get_names_from_archive(self):
        return self.volume.namelist()

    def update(self):
        self.volume.copy_to(os.path.join(self.workdir, self.target))
