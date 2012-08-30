from batou.component import Component
from batou.utils import md5sum
import batou
import os.path
import urlparse


class Download(Component):

    namevar = 'uri'

    target = None  # Filename where the download will be stored.
    md5sum = None

    def configure(self):
        if not self.target:
            self.target = urlparse.urlsplit(self.uri).path.split('/')[-1]
        if not self.target:
            raise KeyError('No target is given and the URI does not allow '
                           'deriving a filename.')
        if not self.md5sum:
            raise KeyError('No MD5 sum for download given.')

    def verify(self):
        if not os.path.exists(self.target):
            raise batou.UpdateNeeded()
        if self.md5sum != md5sum(self.target):
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd('wget -q -O {target} {uri}'.format(
                    target=self.target, uri=self.uri))
        assert self.md5sum == md5sum(self.target)
