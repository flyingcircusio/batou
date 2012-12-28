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

    def _detect_virtualenv(self):
        # Prefer the virtualenv of the target version. There are some
        # incompatibilities between Python and virtualenv versions.
        possible_executables = ['virtualenv-{}'.format(self.version),
                                'virtualenv']
        for executable in possible_executables:
            try:
                self.cmd('type {}'.format(executable))
            except RuntimeError:
                pass
            else:
                break
        else:
            raise RuntimeError('Could not find virtualenv executable')
        return executable

    def update(self):
        executable = self._detect_virtualenv()
        self.cmd('{} --no-site-packages --python python{} .'.format(
                 executable, self.version))
