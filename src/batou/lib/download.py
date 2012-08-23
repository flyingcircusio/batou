from batou.component import Component
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

    def verify_md5(self):
        stdout, stderr = self.cmd('md5sum {}'.format(self.target))
        lines = stdout.splitlines()
        assert len(lines) == 1
        md5, sep, filename = lines[0].partition(' ')
        assert filename.strip() == self.target
        return md5 == self.md5sum

    def verify(self):
        if not os.path.exists(self.target):
            raise batou.UpdateNeeded()
        if not self.verify_md5():
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd('wget -q -O {target} {uri}'.format(
                    target=self.target, uri=self.uri))
        assert self.verify_md5()
