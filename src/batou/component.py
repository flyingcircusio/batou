import batou
import batou.c
import batou.template
import batou.utils
import contextlib
import logging
import os
import os.path
import sys
import types

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
    oldcwd = os.getcwd()
    defdir = os.path.dirname(filename)
    os.chdir(defdir)
    module_name = os.path.basename(defdir)
    module_path = 'batou.c.{}'.format(module_name)
    module = types.ModuleType(module_name,
        'Component definition module for {}'.format(filename))
    sys.modules[module_path] = module
    setattr(batou.c, module_name, module)
    execfile(filename, module.__dict__)

    for candidate in module.__dict__.values():
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
    _prepared = False

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
        self._prepared = True

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

    def last_updated(self):
        """An optional helper to indicate to other components a timestamp how new any changes
        in the target system related to this component are.

        Can be used to determine file ages, etc.
        """
        raise NotImplementedError

    # Sub-component mechanics

    def __add__(self, component):
        """Add a new sub-component.

        This will also automatically prepare the added component if it hasn't
        been prepared yet. Could have been prepared if it was configured in the
        context of a different component.

        """
        if component is not None:
            # Allow `None` components to flow right through. This makes the API a
            # bit more convenient in some cases, e.g. with platform handling.
            self.sub_components.append(component)
            self |= component
            component.parent = self
        return self

    def __or__(self, component):
        """Prepare a component in the context of this component but do not add
        it to the sub components.

        This allows executing 'configure' in the context of this component

        """
        if component is not None and not component._prepared:
            component.prepare(self.service, self.environment,
                              self.host, self.root, self)
        return self

    @property
    def recursive_sub_components(self):
        for sub in self.sub_components:
            yield sub
            for rec_sub in sub.recursive_sub_components:
                yield rec_sub

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

    def require(self, key, host=None, strict=True, reverse=False):
        return self.host.environment.resources.require(
            self.root, key, host, strict, reverse)

    def require_one(self, key, host=None, strict=True, reverse=False):
        resources = self.require(key, host, strict, reverse)
        if len(resources) > 1:
            raise KeyError(
                "Expected only one result, got multiple for (key={}, host={})".
                    format(key, host))
        elif len(resources) == 0:
            raise KeyError(
                "Expected one result, got none for (key={}, host={})".
                    format(key, host))
        return resources[0]

    # Component (convenience) API

    @property
    def workdir(self):
        return self.root.workdir

    # XXX backwards-compatibility. :/
    def assert_file_is_current(self, reference, requirements=[], **kw):
        from batou.lib.file import File
        self.assert_component_is_current(
            File(reference), [File(r) for r in requirements], **kw)

    def assert_component_is_current(self, component, requirements=[], **kw):
        reference = component.last_updated(**kw)
        if reference is None:
            raise batou.UpdateNeeded()
        for requirement in requirements:
            if reference < requirement.last_updated(**kw):
                raise batou.UpdateNeeded()

    def assert_no_subcomponent_changes(self):
        for component in self.sub_components:
            if component.changed:
                raise batou.UpdateNeeded()

    def assert_no_changes(self):
        if self.changed:
            raise batou.UpdateNeeded()
        self.assert_no_subcomponent_changes()

    def cmd(self, cmd, silent=False, ignore_returncode=False):
        return batou.utils.cmd(cmd, silent, ignore_returncode)

    def map(self, path):
        path = os.path.expanduser(path)
        if not path.startswith('/'):
            return os.path.normpath(os.path.join(self.workdir, path))
        return self.environment.map(path)

    def touch(self, filename):
        if os.path.exists(filename):
            os.utime(filename, None)
        else:
            open(filename, 'w').close()

    def expand(self, string, component=None, **kw):
        engine = batou.template.Jinja2Engine()
        args = self._template_args(component=component, **kw)
        return engine.expand(string, args, self._breadcrumbs)

    def template(self, filename, component=None):
        engine = batou.template.Jinja2Engine()
        return engine.template(
            filename, self._template_args(component=component))

    def _template_args(self, component=None, **kw):
        if component is None:
            component = self
        args = dict(
            host=self.host,
            environment=self.environment,
            service=self.service,
            component=component)
        args.update(kw)
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
        root = RootComponent(self.name, factory, self.factory, host, self.defdir)
        if features:
            root.features = features
        return root


class RootComponent(object):
    """Wrapper to manage top-level components assigned to hosts in an
    environment.

    Root components have a name and "own" the working directory for itself and
    its sub-components.

    """

    def __init__(self, name, factory, class_, host, defdir):
        self.factory = factory
        self.class_ = class_
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

    def setup_overrides(self):
        environment = self.host.environment
        if self.name not in environment.overrides:
            return
        for key, value in environment.overrides[self.name].items():
            if not hasattr(self.component, key):
                raise KeyError(
                    'Invalid override attribute "{}" for component {}'.format(
                        key, self.component))
            setattr(self.component, key, value)

    def prepare(self):
        environment = self.host.environment
        environment.resources.reset_component_resources(self)
        self.component = self.factory()
        self.setup_overrides()
        self.component.prepare(
            self.service, environment, self.host, self)

    def deploy(self):
        self._ensure_workdir()
        os.chdir(self.workdir)
        self.component.deploy()
