from batou.component import Component
import batou
import batou.utils
import os.path
import urlparse
import requests
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve


class Download(Component):

    namevar = 'uri'

    target = None  # Filename where the download will be stored.
    checksum = None
    requests_kwargs = None

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
        scheme = urlparse.urlsplit(self.uri)[0]
        if scheme in ['http', 'https']:
            self._update_requests()
        else:
            self._update_urllib()

        target_checksum = batou.utils.hash(self.target, self.checksum_function)
        assert self.checksum == target_checksum, '''\
Checksum mismatch!
expected: %s
got: %s''' % (self.checksum, target_checksum)

    def _update_requests(self):
        r = requests.get(
            self.uri,
            **(self.requests_kwargs if self.requests_kwargs else {}))
        r.raise_for_status()

        with open(self.target, 'wb') as fd:
            for chunk in r.iter_content(4*1024**2):
                fd.write(chunk)

    def _update_urllib(self):
        path, headers = urlretrieve(self.uri, self.target)
        assert path == self.target
