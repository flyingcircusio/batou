from batou.component import Component


class VirtualEnv(Component):

    namevar = 'version'

    @property
    def python(self):
        return 'bin/python{}'.format(self.version)

    def verify(self):
        self.assert_file_is_current(self.python)

    def update(self):
        self.cmd('virtualenv --no-site-packages --python python{} .'.format(
                 self.version))
