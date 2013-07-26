"""Components to manage Python environments."""

from batou import UpdateNeeded
from batou.component import Component
import logging


logger = logging.getLogger(__name__)


class VirtualEnv(Component):
    """Manage a virtualenv installation.
    """

    namevar = 'version'
    _clean = False

    # XXX unsure whether this factoring is OK.
    # Depending on the platform and or environment the python executable may
    # not be in the search path and may not even have a predictable path.

    # Alternatively we could have (Unix) environment variables defined in the
    # (batou) environment definition. (Sounds like a good idea.)

    _venv_python_compatibility = {'2.4': '1.7.2',
                                  '2.5': '1.9'}

    @property
    def python(self):
        """Path to the generated python executable."""
        return 'bin/python{}'.format(self.version)

    def verify(self):
        self.assert_file_is_current(self.python)
        try:
            # If the Python is broken enough, we have to clean it _a lot_
            self.cmd('{} -c "import pkg_resources"'.format(self.python),
                     silent=True)
        except RuntimeError:
            self._clean = True
            raise UpdateNeeded()

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
        if self._clean:
            self.cmd('rm -rf bin/ lib/ include/')
        commandline = self._detect_virtualenv()
        target = '.'
        try:
            self.cmd('{} {}'.format(commandline, target), silent=True)
        except RuntimeError:
            # Sigh. There is a good chance that the Python version we're trying
            # to get virtualenved isn't compatible with this version of
            # virtualenv. We'll have to sacrifice a chicken: create a
            # workaround-virtualenv "whatever works" that we use to downgrade
            # to a specific virtualenv version that we know supports our target
            # python version.
            self.cmd('virtualenv bootstrap-venv')
            with self.chdir('bootstrap-venv'):
                usable_venv = self._venv_python_compatibility.get(self.version)
                if usable_venv:
                    self.cmd('bin/pip install --upgrade virtualenv=={}'.format(
                        usable_venv))
                else:
                    # We don't know a specific version, let's try the most
                    # current one.
                    self.cmd('bin/pip install --upgrade virtualenv')
            self.cmd('bootstrap-venv/bin/virtualenv --python=python{} '
                     '--no-site-packages {}'.format(self.version, target))
            self.cmd('rm -rf bootstrap-venv')


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
        self.cmd('bin/easy_install --upgrade "pip=={}"'.format(self.version))


class Package(Component):

    namevar = 'package'
    version = None

    def verify(self):
        try:
            self.cmd('bin/python -c "import pkg_resources; '
                     'pkg_resources.require(\'{}\')[0].version == \'{}\'"'
                     .format(self.package, self.version), silent=True)
        except RuntimeError, e:
            logger.debug(e[3])
            raise UpdateNeeded()

    def update(self):
        self.cmd('bin/pip --timeout=10 --force-reinstall install '
                 '"{}=={}"'.format(self.package, self.version))

    @property
    def namevar_for_breadcrumb(self):
        return '{}=={}'.format(self.package, self.version)
