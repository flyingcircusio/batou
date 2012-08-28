import batou
import batou.template
import batou.utils
import contextlib
import logging
import os
import os.path
import subprocess

logger = logging.getLogger(__name__)


def platform(name, component):
    """Class decorator to register a component class as a platform-component
    for the given platform and component.
    """
    def register_platform(cls):
        component.add_platform(name, cls)
        return cls
    return register_platform


def load_components_from_file(filename):
    g = l = {}
    oldcwd = os.getcwd()
    defdir = os.path.dirname(filename)
    os.chdir(defdir)
    execfile(filename, g, l)
    for candidate in l.values():
        if candidate in [Component]:
            # Ignore anything we pushed into the globals before execution
            continue
        if (isinstance(candidate, type) and
            issubclass(candidate, Component)):
            factory = RootComponentFactory(
                    candidate.__name__.lower(),
                    candidate,
                    defdir)
            yield factory
    os.chdir(oldcwd)


class Component(object):

    namevar = ''

    changed = False

    def __init__(self, namevar=None, **kw):
        if self.namevar:
            if namevar is None:
                raise ValueError('Namevar %s required' % self.namevar)
            kw[self.namevar] = namevar
        self.__dict__.update(kw)

    # Configuration phase

    def prepare(self, service, environment, host, root, parent=None):
        self.service = service
        self.environment = environment
        self.host = host
        self.root = root
        self.parent = parent
        self.sub_components = []
        self.configure()
        self += self.get_platform()

    def configure(self):
        """Configure the component.

        At this point the component has been embedded into the overall
        structure, so that service, environment, host, root, and parent are
        set.

        Also, any environment-specific attributes have been set.

        At this point the component should add sub-components as required and
        use the configured values so that calls to verify/update can, without
        much overhead, perform their work.

        Also, any computation that happens in the configure phase is run while
        building the model so that this can be used to ensure some level of
        internal consistency before invoking the remote control layer.
        """
        pass

    # Support remote bootstrapping

    def remote_bootstrap(self, remote_host):
        pass

    # Deployment phase

    def deploy(self):
        # Reset changed flag here to support triggering deploy() multiple
        # times.
        self.changed = False
        for sub_component in self.sub_components:
            sub_component.deploy()
            if sub_component.changed:
                self.changed = True
        try:
            self.verify()
        except batou.UpdateNeeded:
            logger.info('Updating {}'.format(self._breadcrumbs))
            self.update()
            self.changed = True

    def verify(self):
        """Verify whether this component has been deployed correctly or needs
        to be updated.

        Raises the UpdateNeeded exception if an update is needed.

        Implemented by specific components.
        """
        pass

    def update(self):
        """Is called if the verify method indicated that an update is needed.

        This method needs to handle all cases to move the current deployed
        state of the component, whatever it is, to the desired new state.

        Implemented by specific components.

        """
        pass

    # Sub-component mechanics

    def __add__(self, component):
        """Add a new sub-component.

        This will also automatically prepare the added component.

        """
        # Allow `None` components to flow right through. This makes the API a
        # bit more convenient in some cases, e.g. with platform handling.
        if component is not None:
            self.sub_components.append(component)
            component.prepare(self.service, self.environment,
                              self.host, self.root, self)
        return self

    # Platform mechanics

    @classmethod
    def add_platform(cls, name, platform):
        if not '_platforms' in cls.__dict__:
            cls._platforms = {}
        cls._platforms[name] = platform

    def get_platform(self):
        """Return the platform component for this component if one exists."""
        platforms = self.__class__.__dict__.get('_platforms', {})
        return platforms.get(self.environment.platform, lambda: None)()

    # Resource provider/user API

    def provide(self, key, value):
        self.host.environment.resources.provide(self.root, key, value)

    def require(self, key, host=None, strict=True):
        return self.host.environment.resources.require(
            self.root, key, host, strict)

    def require_one(self, key, host=None, strict=True):
        resources = self.require(key, host, strict)
        if len(resources) != 1:
            raise KeyError(
                "Expected only one result, got multiple for (key={}, host={})".
                    format(key, host))
        return resources[0]

    # Component (convenience) API

    @property
    def workdir(self):
        return self.root.workdir

    def assert_file_is_current(self, result, requirements=[],
                               attribute='st_mtime'):
        if not os.path.exists(result):
            raise batou.UpdateNeeded()
        current = getattr(os.stat(result), attribute)
        for requirement in requirements:
            if current < getattr(os.stat(requirement), attribute):
                raise batou.UpdateNeeded()

    def assert_no_subcomponent_changes(self):
        for component in self.sub_components:
            if component.changed:
                raise batou.UpdateNeeded()

    def assert_no_changes(self):
        if self.changed:
            raise batou.UpdateNeeded()
        self.assert_no_subcomponent_changes()

    def cmd(self, cmd, silent=False):
        stdin = open('/dev/null')
        process = subprocess.Popen(
            [cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin,
            shell=True)
        stdout, stderr = process.communicate()
        retcode = process.poll()
        if retcode:
            if not silent:
                print "STDOUT"
                print "=" * 72
                print stdout
                print "STDERR"
                print "=" * 72
                print stderr
            raise RuntimeError(
                'Command "{}" returned unsuccessfully.'.format(cmd))
        stdin.close()
        return stdout, stderr

    def map(self, path):
        if not path.startswith('/'):
            return os.path.normpath(os.path.join(self.workdir, path))
        return self.environment.map(path)

    def touch(self, filename):
        if os.path.exists(filename):
            os.utime(filename, None)
        else:
            open(filename, 'w').close()

    def expand(self, string, component=None):
        engine = batou.template.Jinja2Engine()
        return engine.expand(string, self._template_args(component=component))

    def template(self, filename, component=None):
        engine = batou.template.Jinja2Engine()
        return engine.template(
            filename, self._template_args(component=component))

    def _template_args(self, component=None):
        if component is None:
            component = self
        args = dict(
            host=self.host,
            environment=self.environment,
            service=self.service,
            component=component)
        return args

    @contextlib.contextmanager
    def chdir(self, path):
        old = os.getcwd()
        try:
            os.chdir(path)
            yield
        finally:
            # XXX missing test
            os.chdir(old)

    # internal methods

    @property
    def _breadcrumbs(self):
        result = ''
        if self.parent is not None:
            result += self.parent._breadcrumbs + ' > '
        result += self._breadcrumb
        return result

    @property
    def _breadcrumb(self):
        result = self.__class__.__name__
        name = self.namevar_for_breadcrumb
        if name:
            result += '({})'.format(name)
        return result

    @property
    def namevar_for_breadcrumb(self):
        return getattr(self, self.namevar, None)


class HookComponent(Component):
    """A component that provides itself as a resource."""

    def configure(self):
        self.provide(self.key, self)


class RootComponentFactory(object):

    def __init__(self, name, factory, defdir):
        self.name = name
        self.factory = factory
        self.defdir = defdir

    def __call__(self, service, environment, host, features, config):
        factory = lambda: self.factory(**config)
        root = RootComponent(self.name, factory, host, self.defdir)
        if features:
            root.features = features
        return root


class RootComponent(object):
    """Wrapper to manage top-level components assigned to hosts in an
    environment.

    Root components have a name and "own" the working directory for itself and
    its sub-components.

    """

    def __init__(self, name, factory, host, defdir):
        self.factory = factory
        self.name = name
        self.defdir = defdir
        self.host = host
        # XXX law of demeter.
        self.service = self.host.environment.service
        self.environment = self.host.environment

    def __repr__(self):
        return '<%s "%s" object at %s>' % (
            self.__class__.__name__, self.name, id(self))

    @property
    def workdir(self):
        return '%s/%s' % (self.environment.workdir_base, self.name)

    def _ensure_workdir(self):
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)

    def prepare(self):
        environment = self.host.environment
        environment.resources.reset_component_resources(self)
        self.component = self.factory()
        if self.name in environment.overrides:
            self.component.__dict__.update(
                environment.overrides[self.name])
        self.component.prepare(
            self.service, environment, self.host, self)

    def deploy(self):
        self._ensure_workdir()
        os.chdir(self.workdir)
        self.component.deploy()
