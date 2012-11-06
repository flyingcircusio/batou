from batou.component import Component
from batou.utils import hash
import batou
import os.path
import urlparse


class Download(Component):

    namevar = 'uri'

    target = None  # Filename where the download will be stored.
    md5sum = None  # XXX deprecated
    checksum = None

    def configure(self):
        if not self.target:
            self.target = urlparse.urlsplit(self.uri).path.split('/')[-1]
        if not self.target:
            raise KeyError('No target is given and the URI does not allow '
                           'deriving a filename.')
        if self.md5sum:
            raise ValueError('md5sum is deprecated. Use checksum="md5:..."')
        self.checksum_function, self.checksum = self.checksum.split(':')

    def verify(self):
        if not os.path.exists(self.target):
            raise batou.UpdateNeeded()
        if self.checksum != hash(self.target):
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd('wget -q -O {target} {uri}'.format(
                    target=self.target, uri=self.uri))
        assert self.checksum == hash(self.target, self.checksum_function)
