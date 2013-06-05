from batou.component import Component
from batou.lib.file import Directory
from zipfile import ZipFile
import os


class Extract(Component):

    namevar = 'archive'

    create_target_dir = True
    target = None

    strip = 0

    def configure(self):
        for candidate in [Unzip, Untar]:
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
