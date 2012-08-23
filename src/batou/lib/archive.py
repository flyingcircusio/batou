from batou.component import Component
from batou.lib.file import Directory
import os


def archive_base_name(archive):
    for ext in ['.tar.gz', '.tar', '.tar.bz2', '.tgz']:
        if archive.endswith(ext):
            return archive.rsplit(ext, 1)[0]


class Extract(Component):

    namevar = 'archive'

    target = None
    strip = 0

    exclude = ('._*')

    def configure(self):
        if self.target is None:
            self.target = archive_base_name(self.archive)
        if not self.target:
            raise AttributeError(
                "Target not given and not derivable from archive name ({}).".
                    format(self.archive))
        self += Directory(self.target, leading=True)
        self.exclude = ' '.join("--exclude='{}'".format(x) for x in self.exclude)

    def verify(self):
        # If the target directory has just been created, then we need to
        # extract again.
        self.assert_file_is_current(
            self.target, [self.archive], attribute='st_ctime')
        # Check that all files in the directory are newer than the archive.
        # XXX Might also have a problem regarding archive attribute
        # preservation?
        stdout, stderr = self.cmd(self.expand(
            'tar tf {{component.archive}} {{component.exclude}}'))
        for filename in stdout.splitlines():
            filename = os.path.join(*filename.split(os.path.sep)[self.strip:])
            self.assert_file_is_current(
                os.path.join(self.target, filename),
                [self.archive], attribute='st_ctime')

    def update(self):
        self.cmd(self.expand(
            'tar xf {{component.archive}} -C {{component.target}} '
            '--strip-components {{component.strip}}'))
