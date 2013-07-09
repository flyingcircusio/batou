"""Components to manage Python environments."""

from batou.component import Component
from batou import UpdateNeeded
import yaml


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
        possible_executables = [
            ('virtualenv-{}'.format(self.version), '--no-site-packages'),
            ('virtualenv', '--no-site-packages --python python{}'.format(
                self.version))]
        for executable, arguments in possible_executables:
            try:
                self.cmd('type {}'.format(executable), silent=True)
            except RuntimeError:
                pass
            else:
                break
        else:
            raise RuntimeError('Could not find virtualenv executable')
        return '{} {}'.format(executable, arguments)

    def update(self):
        commandline = self._detect_virtualenv()
        target = '.'
        self.cmd('{} {}'.format(commandline, target))


class PIP(Component):

    namevar = 'version'
    version = '1.3'

    def verify(self):
        try:
            result, _ = self.cmd('bin/pip --version')
        except RuntimeError:
            raise UpdateNeeded()
        if not result.startswith('pip {} '.format(self.version)):
            raise UpdateNeeded()

    def update(self):
        self.cmd('bin/pip install --upgrade "pip=={}"'.format(self.version))


class Package(Component):

    namevar = 'package'
    version = None

    def verify(self):
        result, _ = self.cmd('bin/pip show {}'.format(self.package))
        result = result.strip()
        if not result:
            raise UpdateNeeded()
        result = yaml.load(result)
        if result['Version'] != self.version:
            raise UpdateNeeded()

    def update(self):
        self.cmd('bin/pip install --upgrade "{}=={}"'.format(
            self.package, self.version))

    @property
    def namevar_for_breadcrumb(self):
        return '{}=={}'.format(self.package, self.version)
