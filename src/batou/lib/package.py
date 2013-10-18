from batou.component import Component
from batou import UpdateNeeded


class DPKG(Component):
    """Install a dpkg system package.

    This is experimental to get automation started, apt only for now.

    """

    namevar = 'package'

    def verify(self):
        stdout, stderr = self.cmd('LANG=C dpkg --get-selections')
        for line in stdout.splitlines():
            candidate, status = line.split()
            if candidate == self.package and status == 'install':
                break
        else:
            raise UpdateNeeded()

    def update(self):
        # /dev/null: a talky apt-get get blocks remote execution
        self.cmd('LANG=C apt-get -qy install {0}'.format(self.package))
