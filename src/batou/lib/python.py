from batou.component import Component
from batou.lib.download import Download
from batou.lib.archive import Extract
from batou import UpdateNeeded
import sys
import logging
import os.path


logger = logging.getLogger(__name__)


class VirtualEnv(Component):
    """Manage a virtualenv installation.

    This also manages a clean virtualenv installation to ensure we know
    what we're dealing with.

    There is some flexibility WRT asking for specific versions of
    setuptools, distribute, etc.

    It also upgrades the whole virtualenv if the virtualenv version itself
    is upgraded.

    """

    namevar = 'version'

    # XXX unsure whether this factoring is OK.
    # Depending on the platform and or environment the python executable may
    # not be in the search path and may not even have a predictable path.

    # Alternatively we could have (Unix) environment variables defined in the
    # (batou) environment definition. (Sounds like a good idea.)

    def configure(self):
        self.base = VirtualEnvBase()
        self += self.base

    def verify(self):
        # Did we install an updated virtualenv package in between?
        self.assert_file_is_current('bin/python', [self.base.venv_cmd])
        # Is this Python (still) functional 'enough'?
        self.assert_cmd('{} -c "import pkg_resources"'.format(self.python))

    def update(self):
        self.cmd('rm -rf bin/ lib/ include/')
        self.cmd('{} {} --setuptools --python=python{} {}'.format(
            sys.executable, self.base.venv_cmd, self.version, self.workdir))

    @property
    def python(self):
        """Path to the generated python executable."""
        return 'bin/python{}'.format(self.version)


class VirtualEnvBase(Component):

    def configure(self):
        # This will manage one central virtualenv base installation for all
        # components to share.
        self.workdir = self.environment.workdir_base + '/.virtualenv'
        download = Download(
            'http://pypi.gocept.com/packages/source'
            '/v/virtualenv/virtualenv-1.10.1.tar.gz',
            checksum='md5:3a04aa2b32c76c83725ed4d9918e362e')
        self += download
        self += Extract(download.target, target='.')
        extracted_dir = os.path.basename(download.target).rstrip('.tar.gz')
        self.venv_cmd = self.workdir + '/' + extracted_dir + '/virtualenv.py'


class Package(Component):

    namevar = 'package'
    version = None
    check_package_is_module = True
    timeout = None

    # NOTE: this might cause dependencies to be updated without version pins.
    # If this is a problem, introduce a class attribute `dependencies = True`.
    pip_install_options = ('--egg', '--ignore-installed')

    def configure(self):
        if self.timeout is None:
            self.timeout = self.environment.timeout

    def verify(self):
        try:
            self.cmd(
                'bin/python -c "import pkg_resources; '
                'assert pkg_resources.require(\'{}\')[0].version == \'{}\'"'
                .format(self.package, self.version), silent=True)
        except RuntimeError, e:
            logger.debug(e[3])
            raise UpdateNeeded()
        # Is the package usable? Is the package a module?  This might be
        # overspecific - I'm looking for a way to deal with:
        # https://github.com/pypa/pip/issues/3 if a namespace package was not
        # installed cleanly. This only works (currently), when the package name
        # corresponds with what it contains. I.E. it works for zc.buildout but
        # not for distribute, which installs a setuptools package.
        if self.check_package_is_module:
            base_package = self.package.split('.')[0]
            try:
                self.cmd('bin/python -c "import {0};{0}.__file__"'.format(
                    base_package), silent=True)
            except RuntimeError:
                raise UpdateNeeded()

    def update(self):
        options = ' '.join(self.pip_install_options)
        self.cmd('bin/pip --timeout={} install {} '
                 '"{}=={}"'.format(
                     self.timeout, options, self.package, self.version))

    @property
    def namevar_for_breadcrumb(self):
        return '{}=={}'.format(self.package, self.version)
