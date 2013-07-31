from batou.component import Component
from batou import UpdateNeeded
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

    pip_install_options = ['--egg', '--force-reinstall']

    def verify(self):
        # Is the right version installed according to PIP?
        try:
            self.cmd('bin/python -c "import pkg_resources; '
                     'pkg_resources.require(\'{}\')[0].version == \'{}\'"'
                     .format(self.package, self.version), silent=True)
        except RuntimeError, e:
            logger.debug(e[3])
            raise UpdateNeeded()
        # Is the package usable? Is the package a module?  This might be
        # overspecific - I'm looking for a way to deal with:
        # https://github.com/pypa/pip/issues/3 if a namespace package was not
        # installed cleanly.
        base_package = self.package.split('.')[0]
        try:
            self.cmd('bin/python -c "import {0};{0}.__file__'.format(
                     base_package))
        except RuntimeError:
            self.pip_install_options.extend(['-I', '--no-deps'])

    def update(self):
        options = ' '.join(self.pip_install_options)
        self.cmd('bin/pip --timeout=10 install {} '
                 '"{}=={}"'.format(
                     options, self.package, self.version))

    @property
    def namevar_for_breadcrumb(self):
        return '{}=={}'.format(self.package, self.version)
