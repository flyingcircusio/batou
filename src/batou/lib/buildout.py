from batou.component import Component
from batou.lib.file import File
from batou.lib.python import VirtualEnv, Package
import contextlib
import os.path


class Buildout(Component):

    timeout = None
    extends = ()   # Extends need to be components that have a path
    use_default = True
    config = None
    additional_config = ()
    config_file_name = 'buildout.cfg'

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

        venv = VirtualEnv(self.python)
        self += venv
        if self.distribute:
            self += Package(
                'distribute', version=self.distribute,
                check_package_is_module=False)
        if self.setuptools:
            self += Package('setuptools', version=self.setuptools)

        self += Package('zc.buildout', version=self.version)

    def verify(self):
        self.assert_file_is_current('bin/buildout')
        # XXX we can't be sure that all config objects are files!
        installed = File('.installed.cfg')
        self |= installed
        installed.assert_component_is_current(
            [File('bin/buildout')] + self.config)
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
    for key, value in environment.items():
        old_env.setdefault(key, '')
        environment[key] = value.format(**old_env)
    try:
        os.environ.update(environment)
        yield
    finally:
        os.environ.clear()
        os.environ.update(old_env)
