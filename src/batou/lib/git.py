from batou.component import Component
from batou import UpdateNeeded
import os.path
import shutil


class Clone(Component):

    # BBB the namevar used to be target, but all other VCS components have url
    namevar = 'url_or_target'
    url = None
    target = '.'
    source = None  # BBB

    update_unpinned = False

    def configure(self):
        if self.source is None:
            self.url = self.url_or_target
        else:
            self.url = self.source
            self.target = self.url_or_target

        self.git_dir = '{}/.git'.format(self.target)

    def verify(self):
        if not os.path.exists(self.git_dir):
            raise UpdateNeeded()
        if self.update_unpinned:
            raise UpdateNeeded()

    def update(self):
        if (os.path.exists(self.target) and not
                os.path.isdir(self.git_dir)):
            # Clean any non-git residuals
            shutil.rmtree(self.target)
        if not os.path.exists(self.target):
            self.cmd('git clone {0} {1}'.format(self.url, self.target))
        with self.chdir(self.target):
            self.cmd('git pull')
            self.cmd('git submodule update --init --recursive')
