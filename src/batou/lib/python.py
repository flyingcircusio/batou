"""Components to manage Python environments."""

from batou.component import Component


class VirtualEnv(Component):
    """Manage a virtualenv installation.
    """

    namevar = 'version'

    # XXX unsure whether this factoring is OK.
    # Depending on the platform and or environment the python executable may
    # not be in the search path and may not even have a predictable path.

    # Alternatively we could have (Unix) environment variables defined in the
    # (batou) environment definition. (Sounds like a good idea.)

    @property
    def python(self):
        """Path to the generated python executable."""
        return 'bin/python{}'.format(self.version)

    def verify(self):
        self.assert_file_is_current(self.python)

    def update(self):
        self.cmd('virtualenv --no-site-packages --python python{} .'.format(
                 self.version))
