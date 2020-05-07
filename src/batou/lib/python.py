from batou.component import Component
from batou.lib.archive import Extract
from batou.lib.download import Download
from batou.lib.file import ensure_path_nonexistent
from batou.utils import CmdExecutionError
import batou
import hashlib
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
        class_name = 'VirtualEnvPy{}'.format(self.version.replace('.', '_'))
        self.venv = globals().get(class_name, VirtualEnvPy)()
        self += self.venv

        if not self.executable:
            self.executable = 'python{}'.format(self.version)


class VirtualEnvPyBase(Component):

    venv_version = None
    venv_checksum = None
    venv_options = ()

    installer = 'pip'
    install_options = ('--ignore-installed', )

    def verify(self):
        expected_version = tuple(
            int(x) for x in self.parent.version.split('.'))
        version_specificity = len(expected_version)
        self.assert_cmd('bin/python -c "import sys; '
                        'assert sys.version_info[:{}] == {}"'.format(
                            version_specificity, repr(expected_version)))
        # Is this Python (still) functional 'enough'
        # from a setuptools/distribute perspective?
        self.assert_cmd('bin/python -c "import pkg_resources"')

    def update(self):
        self.cmd('chmod -R u+w bin/ lib/ include/ .Python || true')
        self.cmd('rm -rf bin/ lib/ include/ .Python')

    def verify_pkg(self, pkg):
        try:
            self.cmd(
                'bin/python -c "'
                'import pkg_resources; '
                'assert pkg_resources.require(\'{}\')[0].parsed_version == '
                'pkg_resources.parse_version(\'{}\')"'.format(
                    pkg.package, pkg.version))
        except CmdExecutionError:
            raise batou.UpdateNeeded()
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
                raise batou.UpdateNeeded()

    def update_pkg(self, pkg):
        if self.installer == 'pip':
            self.pip_install(pkg)
        else:
            self.easy_install(pkg)

    def pip_install(self, pkg):
        options = self.install_options
        options += pkg.install_options
        if not pkg.dependencies:
            options += ('--no-deps', )
        options = ' '.join(options)
        self.cmd('bin/pip --timeout={} install {} '
                 '"{}=={}"'.format(pkg.timeout, options, pkg.package,
                                   pkg.version),
                 env=pkg.env if pkg.env else {})

    def easy_install(self, pkg):
        # this old installation of pip doesn't support eggs and completely
        # screws up namespace packages. I'm afraid we have to go for
        # easy_install in this case.
        options = self.install_options
        options += pkg.install_options
        if not pkg.dependencies:
            options += ('--no-deps', )
        options = ' '.join(options)
        # XXX does not implement timeout. could we just do this on
        # 'cmd' instead?
        self.cmd('bin/easy_install {} '
                 '"{}=={}"'.format(options, pkg.package, pkg.version),
                 env=pkg.env if pkg.env else {})


class VirtualEnvPy2_7(VirtualEnvPyBase):

    venv_version = '16.7.10'
    venv_checksum = ('sha256:e88fdcb08b0ecb11da97868f463dd'
                     '06275923f50d87f4b9c8b2fc0994eec40f4')
    venv_options = ()

    install_options = ()

    pypi_url = ('https://files.pythonhosted.org/packages/a4/e3/'
                '1f067de470e3a86875ed915438dc3bd781fb0346254'
                'f541190a09472b677/virtualenv-16.7.10.tar.gz')

    def configure(self):
        self.base = VirtualEnvDownload(self.venv_version,
                                       download_url=self.pypi_url,
                                       checksum=self.venv_checksum)
        self += self.base

    def verify(self):
        # Did we install an updated virtualenv package in between?
        self.assert_file_is_current('bin/python', [self.base.venv_cmd])
        super(VirtualEnvPy2_7, self).verify()

    def update(self):
        super(VirtualEnvPy2_7, self).update()
        self.cmd('{} {} {} --python={} {}'.format(self.parent.executable,
                                                  self.base.venv_cmd,
                                                  ' '.join(self.venv_options),
                                                  self.parent.executable,
                                                  self.workdir))


class VirtualEnvPy(VirtualEnvPyBase):
    """VirtualEnv for Python with `-m venv` (>=3.3)"""
    def update(self):
        super(VirtualEnvPy, self).update()
        self.cmd('{} -m venv {}'.format(self.parent.executable, self.workdir))


class VirtualEnvDownload(Component):
    """Manage virtualenv package download and extraction.

    Keeps knowledge about specific virtualenv version.
    """

    namevar = 'version'
    checksum = None
    download_url = ('https://github.com/pypa/virtualenv/archive/'
                    '{{component.version}}.tar.gz')

    def configure(self):
        # This will manage central, version-specific virtualenv base
        # installations for multiple components to share.
        self.workdir = self.environment.workdir_base + '/.virtualenv'
        self += Download(
            self.expand(self.download_url),
            target=self.version + '.tar.gz',  # so Extract knows what to do
            checksum=self.checksum)
        download = self._
        extracted_dir = 'virtualenv-' + self.version
        self += Extract(download.target, target=extracted_dir, strip=1)
        self.venv_cmd = (self.workdir + '/' + extracted_dir + '/virtualenv.py')

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
            raise TypeError('Package() must be added to a virtual environment')
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


class AppEnv(Component):
    """Manage a Python-package based application installation.

    This uses virtualenv and pip with a "lockfile" style requirements.txt
    file.

    Place a file name "requirements.lock" in the defdir and specify the version
    of Python 3 to be used.

    Will automatically rebuild based on hashing of the AppEnv code,
    the requirements file and the chosen version of Python.

    The result is a light-weight 'pseudo' virtualenv with a bin/ directory
    symlinked to the real virtualenv used under the hood.

    """

    namevar = 'python_version'
    env_hash = None

    def configure(self):
        self.requirements = open('requirements.lock', 'r').read()
        hash_content = (
            self.requirements +
            self.python_version +
            open(__file__, 'r').read())
        hash_content = hash_content.encode('utf-8')
        self.env_hash = hashlib.new('sha256', hash_content).hexdigest()
        self.env_dir = os.path.join('.appenv', self.env_hash)
        self.env_ready = os.path.join('.appenv', self.env_hash, 'appenv.ready')

    def verify(self):
        assert os.path.exists(self.env_ready)
        # XXX Check if python is executable

    def update(self):
        ensure_path_nonexistent(self.env_dir)
        if '__PYVENV_LAUNCHER__' in os.environ:
            del os.environ['__PYVENV_LAUNCHER__']
        self.cmd(
            'python{{component.python_version}} -m venv {{component.env_dir}}')
        with open(os.path.join(self.env_dir, 'requirements.lock'), 'w') as req:
            req.write(self.requirements)

        self.pip_path = os.path.join(self.env_dir, 'bin', 'pip3')
        self.cmd(
            '{{component.pip_path}} install --no-deps '
            '-r {{component.env_dir}}/requirements.lock')
        self.cmd('{{component.pip_path}} check')

        with open(self.env_ready, 'w') as f:
            f.write('Ready or not, here I come, you can\'t hide\n')

        self.cmd('ln -sfn {{component.env_hash}} .appenv/current')
        self.cmd('ln -sfn .appenv/current/bin bin')

        for path in os.listdir('.appenv/'):
            if path in (self.env_hash, 'current'):
                continue
            ensure_path_nonexistent(os.path.join('.appenv', path))

    @property
    def namevar_for_breadcrumb(self):
        return self.env_hash
