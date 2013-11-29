from batou.component import Component
import batou
import batou.utils
import os.path
import urlparse
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve


class Download(Component):

    namevar = 'uri'

    target = None  # Filename where the download will be stored.
    checksum = None

    def configure(self):
        if not self.target:
            self.target = urlparse.urlsplit(self.uri).path.split('/')[-1]
        if not self.target:
            raise KeyError('No target is given and the URI does not allow '
                           'deriving a filename.')
        if not self.checksum:
            raise ValueError('No checksum given.')
        self.checksum_function, self.checksum = self.checksum.split(':')

    def verify(self):
        if not os.path.exists(self.target):
            raise batou.UpdateNeeded()
        if self.checksum != batou.utils.hash(self.target,
                                             self.checksum_function):
            raise batou.UpdateNeeded()

    def update(self):
        path, headers = urlretrieve(self.uri, self.target)
        assert path == self.target
        target_checksum = batou.utils.hash(self.target, self.checksum_function)
        assert self.checksum == target_checksum, '''\
Checksum mismatch!
expected: %s
got: %s''' % (self.checksum, target_checksum)
