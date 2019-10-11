from batou.component import Component
from batou.lib.file import File, Presence
from batou.lib.python import VirtualEnv, Package
import contextlib
import os


class Buildout(Component):

    timeout = None
    use_default = True
    config = None
    additional_config = ()
    config_file_name = 'buildout.cfg'

    python = None
    executable = None
    distribute = None
    setuptools = None
    version = None

    build_env = {}  # XXX not frozen. :/

    def configure(self):
        if self.timeout is None:
            self.timeout = self.environment.timeout
        if self.use_default and not self.config:
            # We expect that your definition directory has a buildout.cfg
            self.config = File('buildout.cfg',
                               template_context=self.parent)
        if isinstance(self.config, File):
            self.config_file_name = self.config.path
        if isinstance(self.config, Component):
            self.config = [self.config]
        if not self.config:
            self.config = []
        self.config.extend(self.additional_config)
        for component in self.config:
            self += component

        venv = VirtualEnv(self.python, executable=self.executable)
        self += venv

        if not (self.distribute or self.setuptools):
            raise ValueError(
                'Either setuptools or distribute version must be specified')

        if self.distribute:
            venv += Package('distribute',
                            version=self.distribute,
                            check_package_is_module=False)

        if self.setuptools:
            venv += Package('setuptools',
                            version=self.setuptools)

        # Install without dependencies (that's just setuptools anyway), since
        # that could cause pip to pull in the latest version of setuptools,
        # regardless of the version we wanted to be installed above.
        venv += Package(
            'zc.buildout',
            version=self.version,
            dependencies=False)

    def verify(self):
        self.assert_file_is_current('bin/buildout')
        # XXX we can't be sure that all config objects are files!
        installed = Presence('.installed.cfg')
        self |= installed
        installed.assert_component_is_current(
            [Presence('bin/buildout')] + self.config)
        self.assert_file_is_current(
            '.batou.buildout.success', ['.installed.cfg'])
        self.assert_no_subcomponent_changes()

    def update(self):
        with safe_environment(self.build_env):
            self.cmd('bin/buildout -t {} -c "{}"'.format(
                self.timeout, self.config_file_name))
            self.touch('.batou.buildout.success')


@contextlib.contextmanager
def safe_environment(environment):
    old_env = os.environ.copy()
    for key, value in list(environment.items()):
        old_env.setdefault(key, '')
        environment[key] = value.format(**old_env)
    try:
        os.environ.update(environment)
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)
