from batou import UpdateNeeded
from batou.component import Component
from batou.lib.archive import Extract
from batou.lib.download import Download
from batou.utils import CmdExecutionError
import os.path


class VirtualEnv(Component):
    """Manage a virtualenv installation.

    This also manages a clean virtualenv base installation to ensure we know
    what we're dealing with.

    The virtualenv provides a somewhat abstract interface to specify packages
    to be installed. It tries to use reasonably safe defaults for calling the
    virtualenv, pip, etc. commands.

    It also upgrades the whole virtualenv if the virtualenv version itself is
    upgraded.

    """

    # The Python major version that is requested.
    namevar = 'version'

    # A specific executable to use as the base Python installation to create a
    # virtualenv from. Default: discover they 'python{version}' binary from the
    # search path.
    executable = None

    @property
    def python(self):
        """Path to the generated python executable."""
        return 'bin/python{}'.format(self.version)

    def configure(self):
        self.venv = globals()[
            'VirtualEnvPy{}'.format(self.version.replace('.', '_'))]()
        self += self.venv

        if not self.executable:
            self.executable = 'python{}'.format(self.version)


class VirtualEnvPyBase(Component):

    venv_version = None
    venv_checksum = None
    venv_options = ()

    installer = 'pip'
    install_options = ('--ignore-installed',)

    def configure(self):
        self.base = VirtualEnvDownload(
            self.venv_version,
            checksum=self.venv_checksum)
        self += self.base

    def verify(self):
        # Did we install an updated virtualenv package in between?
        self.assert_file_is_current('bin/python', [self.base.venv_cmd])
        # Is this Python (still) functional 'enough'
        # from a setuptools/distribute perspective?
        self.assert_cmd('bin/python -c "import pkg_resources"')

    def update(self):
        self.cmd('rm -rf bin/ lib/ include/ .Python')
        self.cmd('{} {} {} --python={} {}'.format(
            self.parent.executable,
            self.base.venv_cmd,
            ' '.join(self.venv_options),
            self.parent.executable, self.workdir))

    def verify_pkg(self, pkg):
        try:
            self.cmd(
                'bin/python -c "import pkg_resources; '
                'assert pkg_resources.require(\'{}\')[0].version == \'{}\'"'
                .format(pkg.package, pkg.version))
        except CmdExecutionError:
            raise UpdateNeeded()
        # Is the package usable? Is the package a module?  This might be
        # overspecific - I'm looking for a way to deal with:
        # https://github.com/pypa/pip/issues/3 if a namespace package was not
        # installed cleanly. This only works (currently), when the package name
        # corresponds with what it contains. I.E. it works for zc.buildout but
        # not for distribute, which installs a setuptools package.
        if pkg.check_package_is_module:
            try:
                self.cmd('bin/python -c "import pkg_resources; '
                         'import {0};{0}.__file__"'.format(pkg.package))
            except CmdExecutionError:
                raise UpdateNeeded()

    def update_pkg(self, pkg):
        if self.installer == 'pip':
            self.pip_install(pkg)
        else:
            self.easy_install(pkg)

    def pip_install(self, pkg):
        options = self.install_options
        options += pkg.install_options
        if not pkg.dependencies:
            options += ('--no-deps',)
        options = ' '.join(options)
        self.cmd('bin/pip --timeout={} install {} '
                 '"{}=={}"'.format(
                     pkg.timeout, options, pkg.package, pkg.version),
                 env=pkg.env if pkg.env else {})

    def easy_install(self, pkg):
        # this old installation of pip doesn't support eggs and completely
        # screws up namespace packages. I'm afraid we have to go for
        # easy_install in this case.
        options = self.install_options
        options += pkg.install_options
        if not pkg.dependencies:
            options += ('--no-deps',)
        options = ' '.join(options)
        # XXX does not implement timeout. could we just do this on
        # 'cmd' instead?
        self.cmd('bin/easy_install {} '
                 '"{}=={}"'.format(options, pkg.package, pkg.version),
                 env=pkg.env if pkg.env else {})


class VirtualEnvPy2_4(VirtualEnvPyBase):

    venv_version = '1.7.2'
    venv_checksum = 'md5:b5d63b05373a4344ae099a68875aae78'
    venv_options = ('--no-site-packages',)

    installer = 'easy_install'
    install_options = ()


class VirtualEnvPy2_5(VirtualEnvPyBase):

    venv_version = '1.9.1'
    venv_checksum = 'md5:07e09df0adfca0b2d487e39a4bf2270a'
    venv_options = ('--setuptools', )

    install_options = ('--ignore-installed', '--egg')

    def configure(self):
        super(VirtualEnvPy2_5, self).configure()
        self.parent += Package(
            'ssl',
            version='1.16',
            install_options=('--insecure',))


class VirtualEnvPy2_6(VirtualEnvPyBase):

    venv_version = '1.10.1'
    venv_checksum = 'md5:3a04aa2b32c76c83725ed4d9918e362e'

    install_options = ('--ignore-installed', '--egg')


class VirtualEnvPy2_7(VirtualEnvPyBase):

    venv_version = '13.1.2'
    venv_checksum = 'md5:b989598f068d64b32dead530eb25589a'

    install_options = ('--egg', )


class VirtualEnvPy3_2(VirtualEnvPyBase):

    venv_version = '13.1.2'
    venv_checksum = 'md5:b989598f068d64b32dead530eb25589a'

    install_options = ('--egg', )


class VirtualEnvPy3_3(VirtualEnvPyBase):

    venv_version = '13.1.2'
    venv_checksum = 'md5:b989598f068d64b32dead530eb25589a'

    install_options = ('--egg', )


class VirtualEnvPy3_4(VirtualEnvPyBase):

    venv_version = '13.1.2'
    venv_checksum = 'md5:b989598f068d64b32dead530eb25589a'

    install_options = ('--egg', )


class VirtualEnvPy3_5(VirtualEnvPyBase):

    venv_version = '13.1.2'
    venv_checksum = 'md5:b989598f068d64b32dead530eb25589a'

    install_options = ('--egg', )


class VirtualEnvDownload(Component):
    """Manage virtualenv package download and extraction.

    Keeps knowledge about specific virtualenv version.
    """

    namevar = 'version'
    checksum = None

    url = (
        'https://pypi.fcio.net/packages/source/v/virtualenv/'
        'virtualenv-{}.tar.gz')

    def configure(self):
        # This will manage central, version-specific virtualenv base
        # installations for multiple components to share.
        self.workdir = self.environment.workdir_base + '/.virtualenv'
        download = Download(
            self.url.format(self.version),
            checksum=self.checksum)
        self += download
        self += Extract(download.target, target='.')
        extracted_dir = os.path.basename(download.target).rstrip('.tar.gz')
        self.venv_cmd = self.workdir + '/' + extracted_dir + '/virtualenv.py'

    def verify(self):
        self.assert_no_subcomponent_changes()

    def update(self):
        self.touch(self.venv_cmd)


class Package(Component):
    """Install a package into a virtual python environment.

    Assumes the parent component is a virtual env component.

    """

    namevar = 'package'
    version = None
    check_package_is_module = True
    timeout = None
    dependencies = True
    env = None

    # Additional options to pass to the installer. Installer depends on venv.
    install_options = ()

    def configure(self):
        if not isinstance(self.parent, VirtualEnv):
            raise TypeError(
                'Package() must be added to a virtual environment')
        if self.timeout is None:
            self.timeout = self.environment.timeout

    # Actual verify/update is delegated the specific virtualenv implementation.
    def verify(self):
        self.parent.venv.verify_pkg(self)

    def update(self):
        self.parent.venv.update_pkg(self)

    @property
    def namevar_for_breadcrumb(self):
        return '{}=={}'.format(self.package, self.version)
