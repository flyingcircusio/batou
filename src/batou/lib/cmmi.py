from batou.component import Component
from batou.lib.archive import Extract
from batou.lib.download import Download
import os.path


class Configure(Component):
    # XXX not convergent when changing args

    namevar = 'path'
    args = ''
    prefix = None
    build_environment = None

    def configure(self):
        if self.prefix is None:
            self.prefix = self.workdir

    def verify(self):
        # This is guesswork. Unfortunately CMMI doesn't work any better.
        self.assert_file_is_current(self.path + '/config.status')
        self.assert_file_is_current(
            self.path + '/.batou.config.success',
            [self.path + '/configure'])

    def update(self):
        with self.chdir(self.path):
            self.cmd(self.expand(
                './configure --prefix={{component.prefix}} '
                '{{component.args}}'), env=self.build_environment)
            self.touch('.batou.config.success')


class Make(Component):

    namevar = 'path'
    build_environment = None

    def verify(self):
        self.assert_file_is_current(
            self.path + '/.batou.make.success', [self.path + '/Makefile'])

    def update(self):
        with self.chdir(self.path):
            self.cmd('make install', env=self.build_environment)
            self.touch('.batou.make.success')


class Build(Component):
    """Complex build definition for

    - downloading
    - extracting
    - configure
    - make install

    """

    namevar = 'uri'
    checksum = None
    configure_args = ''
    prefix = None
    build_environment = None

    def configure(self):
        download = Download(
            self.uri, checksum=self.checksum)
        self += download

        extract = Extract(download.target, strip=1)
        self += extract

        self += Configure(extract.target,
                          args=self.configure_args, prefix=self.prefix,
                          build_environment=self.build_environment)
        self += Make(extract.target, build_environment=self.build_environment)

    @property
    def namevar_for_breadcrumb(self):
        return os.path.basename(self.uri)
