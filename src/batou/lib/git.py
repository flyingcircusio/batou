from batou.component import Component
from batou import UpdateNeeded
import os.path
import shutil


class Clone(Component):

    namevar = 'target'
    update_unpinned = False

    def configure(self):
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
            self.cmd('git clone {0} {1}'.format(self.source, self.target))
        with self.chdir(self.target):
            self.cmd('git pull')
            self.cmd('git submodule update --init --recursive')
