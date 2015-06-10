import ast
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
import weakref

logger = logging.getLogger(__name__)


def platform(name, component):
    """Class decorator to register a component class as a platform-component
    for the given platform and component.
    """
    def register_platform(cls):
        component.add_platform(name, cls)
        return cls
    return register_platform


def handle_event(event, scope):
    def wrapper(f):
        f._event = dict(event=event, scope=scope)
        return f
    return wrapper


def check_event_scope(scope, source, target):
    if scope == '*':
        return True
    if scope == 'precursor':
        for candidate in source.root.component.recursive_sub_components:
            if candidate is target:
                break
            if candidate is source:
                # It's only a predecessor if it comes before us
                # and is in the same root.
                return True
        return False
    raise ValueError('Unknown event scope: {}'.format(scope))


def load_components_from_file(filename):
    # XXX protect against loading the same component name multiple times.
    components = {}

    defdir = os.path.dirname(filename)
    module_name = os.path.basename(defdir)
    module_path = 'batou.c.{}'.format(module_name)
    module = types.ModuleType(
        module_name, 'Component definition module for {}'.format(filename))
    sys.modules[module_path] = module
    setattr(batou.c, module_name, module)
    execfile(filename, module.__dict__)

    for candidate in module.__dict__.values():
        if candidate in [Component]:
            # Ignore anything we pushed into the globals before execution
            continue
        if not (isinstance(candidate, type) and
                issubclass(candidate, Component)):
            continue
        candidate.defdir = defdir
        components[candidate.__name__.lower()] = candidate

    return components


class Component(object):

    namevar = ''

    workdir = None

    # Keeps track of the last added component so you can
    # avoid giving temporary names to components.
    _ = None

    changed = False
    _prepared = False

    def __init__(self, namevar=None, **kw):
        if self.namevar:
            if namevar is None:
                raise ValueError('Namevar %s required' % self.namevar)
            kw[self.namevar] = namevar
        self.__dict__.update(kw)

    @property
    def host(self):
        return self.root.host

    @property
    def environment(self):
        return self.root.environment

    # Configuration phase

    def prepare(self, root, parent=None, overrides={}):
        # XXX why can parent be None? Can the root be the last parent?
        # Can't the direct access to root be removed here?
        self.root = root
        self.parent = parent
        if parent:
            self.workdir = parent.workdir
        else:
            self.workdir = root.workdir
        self.sub_components = []
        self._overrides(overrides)
        self.configure()
        self += self.get_platform()
        self.__setup_event_handlers__()
        self._prepared = True

    def _overrides(self, overrides={}):
        for key, value in overrides.items():
            # This 'in dir()' is on purpose, avoiding a hasattr() which
            # triggers the attribute accessor protocol which in turn can cause
            # expensive/volatile conversions, like DNS lookups for the Address
            # type. Overrides need to be able to avoid the originals to be
            # triggered, e.g. if the default DNS doesn't resolve when being
            # offline working on Vagrant.
            if key not in dir(self):
                raise KeyError(
                    'Invalid override attribute "{}" for component {}'.format(
                        key, self))
            setattr(self, key, value)

    def configure(self):
        """Configure the component.

        At this point the component has been embedded into the overall
        structure, so that environment, host, root, and parent are set.

        Also, any environment-specific attributes have been set.

        At this point the component should add sub-components as required and
        use the configured values so that calls to verify/update can, without
        much overhead, perform their work.

        Also, any computation that happens in the configure phase is run while
        building the model so that this can be used to ensure some level of
        internal consistency before invoking the remote control layer.
        """
        pass

    # Deployment phase

    # We're context managers - to allow components to do setup/teardown nicely.

    def __enter__(self):
        pass

    def __exit__(self, type, value, tb):
        pass

    def deploy(self):
        # Remember: this is a tight loop - we need to keep this code fast.

        # Reset changed flag here to support triggering deploy() multiple
        # times. This is mostly helpful for testing, but who know.
        self.changed = False
        for sub_component in self.sub_components:
            sub_component.deploy()
            if sub_component.changed:
                self.changed = True

        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        with self.chdir(self.workdir), self:
            try:
                with batou.utils.Timer(
                        '{} verify()'.format(self._breadcrumbs)):
                    self.verify()
            except batou.UpdateNeeded:
                self.__trigger_event__('before-update')
                logger.info(u'Updating {}'.format(self._breadcrumbs))
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
        """An optional helper to indicate to other components a timestamp how
        new any changes in the target system related to this component are.

        Can be used to determine file ages, etc.
        """
        raise NotImplementedError

    # Event handling mechanics

    def __setup_event_handlers__(self):
        self._event_handlers = handlers = {}
        for candidate in dir(self):
            try:
                candidate = getattr(self, candidate)
            except Exception:
                continue
            if not hasattr(candidate, '_event'):
                continue
            handler = candidate
            if not isinstance(handler._event, dict):
                continue
            handlers.setdefault(handler._event['event'], []).append(handler)

    def __trigger_event__(self, event):
        # We notify all components that belong to the same
        # root.
        for target in self.root.component.recursive_sub_components:
            for handler in target._event_handlers.get(event, []):
                if not check_event_scope(
                        handler._event['scope'], self, target):
                    continue
                handler(self)

    # Sub-component mechanics

    def __add__(self, component):
        """Add a new sub-component.

        This will also automatically prepare the added component if it hasn't
        been prepared yet. Could have been prepared if it was configured in the
        context of a different component.

        """
        if component is not None:
            # Allow `None` components to flow right through. This makes the API
            # a bit more convenient in some cases, e.g. with platform handling.
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
            component.prepare(self.root, self)
        self._ = component
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
        self.environment.resources.provide(self.root, key, value)

    def require(self, key, host=None, strict=True, reverse=False, dirty=False):
        return self.environment.resources.require(
            self.root, key, host, strict, reverse, dirty)

    def require_one(self, key, host=None, strict=True, reverse=False,
                    dirty=False):
        resources = self.require(key, host, strict, reverse, dirty)
        if len(resources) > 1:
            raise KeyError(
                'Expected only one result, got multiple for (key={}, host={})'.
                format(key, host))
        elif len(resources) == 0:
            raise KeyError(
                'Expected one result, got none for (key={}, host={})'.
                format(key, host))
        return resources[0]

    def assert_cmd(self, *args, **kw):
        try:
            kw['silent'] = True
            self.cmd(*args, **kw)
        except RuntimeError:
            raise batou.UpdateNeeded()

    def assert_file_is_current(self, reference, requirements=[], **kw):
        from batou.lib.file import BinaryFile
        reference = BinaryFile(reference)
        self |= reference
        reference.assert_component_is_current(
            [BinaryFile(r) for r in requirements], **kw)

    def assert_component_is_current(self, requirements=[], **kw):
        if isinstance(requirements, Component):
            requirements = [requirements]
        reference = self.last_updated(**kw)
        if reference is None:
            logger.debug('assert_component_is_current({}, ...): No reference'.
                         format(self._breadcrumb))
            raise batou.UpdateNeeded()
        for requirement in requirements:
            self |= requirement
            required = requirement.last_updated(**kw)
            if reference < required:
                logger.debug('assert_component_is_current({}, {}): {} < {}'.
                             format(self._breadcrumb, requirement._breadcrumb,
                                    reference, required))
                raise batou.UpdateNeeded()

    def assert_no_subcomponent_changes(self):
        for component in self.sub_components:
            if component.changed:
                raise batou.UpdateNeeded()

    def assert_no_changes(self):
        if self.changed:
            raise batou.UpdateNeeded()
        self.assert_no_subcomponent_changes()

    def cmd(self, cmd, silent=False, ignore_returncode=False,
            communicate=True, env=None, expand=True):
        if expand:
            cmd = self.expand(cmd)
        return batou.utils.cmd(
            cmd, silent, ignore_returncode, communicate, env)

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


class RootComponent(object):
    """Wrapper to manage top-level components assigned to hosts in an
    environment.

    Root components have a name and determine the initial working directory
    of the sub-components.

    """

    def __init__(self, name, environment, host, features):
        self.name = name
        self.environment = environment
        self.host = host
        self.features = features

    # XXX Should we turn this around and make the environment responsible for
    # putting those attributes on the root?

    @property
    def defdir(self):
        return self.environment.components[self.name].defdir

    @property
    def workdir(self):
        return os.path.join(
            self.environment.workdir_base, self.name)

    def prepare(self):
        self.component = self.environment.components[self.name]()
        if self.features:
            self.component.features = self.features

        overrides = {}
        if self.name in self.environment.overrides:
            overrides.update(self.environment.overrides[self.name].items())

        self.component.prepare(self, overrides=overrides)

    def __repr__(self):
        return '<%s "%s" object at %s>' % (
            self.__class__.__name__, self.name, id(self))


# Overridable component attributes

ATTRIBUTE_NODEFAULT = object()


class Attribute(object):
    """An attribute descriptor is used to provide:

    - declare overrideability for components
    - provide type-conversion from overrides that are strings
    - provide a default.

    The default is not passed through the type conversion.

    Conversion can be given as a string to indicate a built-in conversion:

        literal - interprets the string as a Python literal

    If conversion is a function the function will be used for the conversion.

    The obj is expected to be a "Component" so that 'expand' can be accessed.

    """

    def __init__(self,
                 conversion=None,
                 default=ATTRIBUTE_NODEFAULT,
                 expand=True,
                 map=False):
        if isinstance(conversion, str):
            conversion = getattr(self, 'convert_{}'.format(conversion))
        self.conversion = conversion
        self.default = default
        self.expand = expand
        self.map = map
        self.instances = weakref.WeakKeyDictionary()

    def __get__(self, obj, objtype=None):
        if obj not in self.instances:
            if self.default is ATTRIBUTE_NODEFAULT:
                raise AttributeError()
            self.__set__(obj, self.default)
        return self.instances[obj]

    def __set__(self, obj, value):
        if isinstance(value, basestring) and self.expand:
            value = obj.expand(value)
        if isinstance(value, basestring) and self.map:
            value = obj.map(value)
        if isinstance(value, basestring) and self.conversion:
            value = self.conversion(value)
        self.instances[obj] = value

    def convert_literal(self, value):
        return ast.literal_eval(value)

    def convert_list(self, value):
        l = value.split(',')
        l = [x.strip() for x in l]
        l = filter(None, l)
        return l
