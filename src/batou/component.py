# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.template import TemplateEngine
import batou.utils
import contextlib
import filecmp
import os
import os.path
import re
import shutil
import subprocess


class Component(object):

    configured = False
    defdir = None  # The component's definition directory
    template_format = 'mako'
    features = ()

    @classmethod
    def from_file(cls, filename):
        g = l = {}
        g.update(globals())
        oldcwd = os.getcwd()
        defdir = os.path.dirname(filename)
        os.chdir(defdir)
        execfile(filename, g, l)
        for candidate in l.values():
            if candidate in globals().values():
                continue
            if not isinstance(candidate, type):
                continue
            if issubclass(candidate, Component):
                candidate.defdir = defdir
                yield candidate, candidate.__name__.lower()
        os.chdir(oldcwd)

    def __init__(self, name, host, features, config, template_format=None):
        self.host = host
        self.environment = host.environment
        self.service = host.environment.service
        self.name = name
        self.config = config
        self.hooks = {}
        self.setup_hooks()
        self.features = features
        self.changed_files = set()
        if template_format:
            self.template_format = template_format
        self.template_engine = TemplateEngine.get(self.template_format)

    def setup_hooks(self):
        """Declare this component's hooks."""

    def configure(self):
        """Prepare this component's configuration.

        Perform any processing of configuration options, information
        retrieval from other components, template expansion, etc, so
        that we get ready to deploy this component.
        """
        pass  # override in subclasses

    def _configure(self):
        if self.configured:
            return
        self.configured = True
        self.configure()

    # Convenience API

    @property
    def compdir(self):
        return '%s/work/%s' % (self.service.base, self.name)

    def find_hooks(self, required_name, host=None):
        hooks = []
        required_name = re.compile(required_name)
        for candidate_host in self.host.environment.hosts.values():
            if host and candidate_host is not host:
                continue
            for component in candidate_host.components:
                for name, hook in component.hooks.items():
                    if required_name.match(name):
                        # Ensure that if some component is requested, we will
                        # always return components that have been configured
                        # previously.
                        component._configure()
                        if name not in component.hooks.keys():
                            # Configuration may have caused hook to be
                            # disabled.
                            continue
                        hook._name = name
                        hooks.append(hook)
        if not hooks:
            raise RuntimeError('No hook found: name=%s, host=%s' %
                               (required_name.pattern, host))
        return iter(hooks)

    def config_attr(self, name, datatype='str'):
        value = self.config.get(name, getattr(self, name, ''))
        value = self.expand(str(value))
        value = batou.utils.convert_type(value, datatype)
        setattr(self, name, value)
        return value

    def cmd(self, cmd):
        self.log('%s: cmd: %s' % (os.getcwd(), cmd))
        output = subprocess.check_output([cmd], shell=True)
        self.log(output)
        return output

    def changed_file(self, filename):
        """Add `filename` to the list of changed files."""
        self.changed_files.add(filename)

    def create_leading_dirs(self, targetfile):
        try:
            os.makedirs(os.path.dirname(targetfile))
        except OSError:
            # ignore failures as long as we get the file in place
            pass

    def install(self, source, target, mode=None, makedirs=True):
        """Copy file, chmod optionally, create leading directories."""
        if makedirs:
            self.create_leading_dirs(target)
        if not os.path.exists(target) or not filecmp.cmp(source, target):
            shutil.copyfile(source, target)
            self.changed_file(target)
        if mode and os.stat(target).st_mode & 0o7777 != mode:
            os.chmod(target, mode)
            self.changed_file(target)

    @contextlib.contextmanager
    def chdir(self, directory):
        """Execute associated with block in `directory`."""
        olddir = os.getcwd()
        os.chdir(directory)
        yield
        os.chdir(olddir)

    def log(self, msg):
        print msg.strip()

    # Template API

    @property
    def _template_args(self):
        args = dict(
            host=self.host,
            environment=self.environment,
            service=self.environment.service,
            component=self)
        return args

    def template(self, filename, target):
        """Render template from `filename` into `target` file."""
        changed = self.template_engine.template(filename, target,
                                                self._template_args)
        if changed:
            self.changed_file(target)

    def expand(self, templatestr):
        """Return rendered string template as string."""
        return self.template_engine.expand(templatestr, self._template_args)

    # Multi-step deployment strategy

    def _update_compdir(self):
        if not os.path.exists(self.compdir):
            os.makedirs(self.compdir)
        for dirpath, dirnames, filenames in os.walk(self.defdir):
            working_dirpath = dirpath.replace(self.defdir, self.compdir)
            for dirname in dirnames:
                dirname = os.path.join(working_dirpath, dirname)
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                    self.changed_file(dirname)
            for filename in filenames:
                source_filename = os.path.join(dirpath, filename)
                dest_filename = os.path.join(working_dirpath, filename)
                # Check whether file is up to date at target already.
                if not os.path.exists(dest_filename):
                    pass
                elif (open(source_filename, 'r').read() !=
                      open(dest_filename, 'r').read()):
                    pass
                elif (os.stat(dest_filename).st_mode !=
                      os.stat(source_filename).st_mode):
                    pass
                else:
                    # The target file is up-to-date.
                    continue
                shutil.copy(source_filename, dest_filename)
                self.changed_file(dest_filename)

    def deploy(self):
        """Run all methods annotated with @step(n) in sequence."""
        self.log('deploy: %s' % self.__class__.__name__)
        self._update_compdir()
        os.chdir(self.compdir)
        for step in self.steps():
            self.log('step: %s' % step.__name__)
            step()

    def steps(self):
        """Return ordered list of deployment steps."""
        steps = []
        for name in dir(self):
            f = getattr(self, name)
            if not callable(f):
                continue
            if not getattr(f, 'step', False):
                continue
            steps.append(f)
        steps.sort(key=lambda x: x.step)
        return steps


def step(x):
    def decorate_step(f):
        f.step = x
        return f
    return decorate_step


class Buildout(Component):

    python = 'python2.6'    # which python to use for virtualenv
    executable = None       # path to executable generated by virtualenv
    profile = 'base'

    def configure(self):
        self.config_attr('profile')
        self.find_links = ''

    @property
    def executable(self):
        return 'bin/%s' % self.python

    @property
    def py_version(self):
        return self.python.strip('python')

    def _install_virtualenv(self):
        self.cmd('virtualenv --no-site-packages --python %s .' % self.python)

    def _python_config_candidates(self):
        """List possible file names for python-config."""
        return [cand % dict(py_version=self.py_version) for cand in (
            'python%(py_version)s-config',
            'python-config-%(py_version)s',
            'python-config%(py_version)s',
        )]

    def _install_python_config(self):
        """Create symlink to correct python-config in virtualenv."""
        script_path = subprocess.check_output([
            "%s -c 'from distutils import sysconfig; "
            "print(sysconfig.EXEC_PREFIX)'" % self.python], shell=True).strip()
        for candidate in self._python_config_candidates():
            candidate = os.path.join(script_path, 'bin', candidate)
            if not os.path.exists(candidate):
                continue
            os.symlink(candidate, 'bin/python-config')
            break
        else:
            raise RuntimeError('cannot find suitable python-config',
                               self._python_config_candidates())

    @step(1)
    def install(self):
        """Basic prerequisites: python virtual and supporting files."""
        if not os.path.exists(self.executable):
            self._install_virtualenv()
        if not os.path.islink('bin/python-config'):
            try:
                os.unlink('bin/python-config')
            except OSError:
                pass
            self._install_python_config()

    @step(2)
    def generate_config(self):
        try:
            secrets = self.find_hooks('secrets').next()
            self.find_links = secrets.get('buildout', 'find-links')
        except Exception:
            print('missing [buildout]find-links in secrets file, ignoring')
        self.template('buildout.cfg.in', target='buildout.cfg')

    @step(3)
    def bootstrap(self):
        if os.path.exists('bin/buildout') and (
                os.stat(self.executable).st_mtime <
                os.stat('bin/buildout').st_mtime):
            return
        self.cmd('%s bootstrap.py' % self.executable)

    @step(4)
    def buildout(self):
        output = self.cmd('bin/buildout -t 15')
        # Special case for handling mr.developer exits
        # can be removed once https://bugs.launchpad.net/zc.buildout/+bug/962169
        # is fixed.
        if 'mr.developer: There have been errors, see messages' in output:
            raise RuntimeError('mr.developer encountered an error.')
