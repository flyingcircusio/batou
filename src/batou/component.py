from batou import output, DuplicateComponent
from batou import SilentConfigurationError
import ast
import batou
import batou.c
import batou.template
import batou.utils
import contextlib
import inspect
import os
import os.path
import sys
import types
import weakref


def platform(name, component):
    """Class decorator to register a component class as a platform-component
    for the given platform and component.
    """
    def register_platform(cls):
        component._add_platform(name, cls)
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


class ComponentDefinition(object):

    def __init__(self, factory, filename=None, defdir=None):
        self.factory = factory
        self.name = factory.__name__.lower()
        self.filename = filename if filename else inspect.getfile(factory)
        self.defdir = defdir if defdir else os.path.dirname(self.filename)


def load_components_from_file(filename):
    components = {}

    # Synthesize a module for this component file in batou.c
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
            continue
        if not (isinstance(candidate, type) and
                issubclass(candidate, Component)):
            continue
        compdef = ComponentDefinition(candidate, filename, defdir)
        if compdef.name in components:
            raise DuplicateComponent(compdef)
        components[compdef.name] = compdef

    return components


class Component(object):
    """A component that models configuration and can apply it.

    Use sub-classes of :py:class:`Component` to create custom
    components.

    The constructor takes one un-named argument which is
    assigned to the attribute set by the ``namevar`` class
    attribute.

    The remaining keyword arguments are set as object
    attributes.

    If a component is used as a sub-component (via ``+=``), then
    the constructor arguments sets the object attributes. If a
    component is used directly from an environment
    (becoming a root component) then the constructor is
    called without arguments and overrides from the
    environment and the secrets are set through an
    internal mechanism.

    """

    #: The ``namevar`` attribute specifies the attribute
    #: name of the first unnamed argument passed to the
    #: constructor.
    #:
    #: This helps making components more readable by providing
    #: one "natural" first argument:
    #:
    #: .. code-block:: python
    #:
    #:   class File(Component):
    #:
    #:       namevar = 'filename'
    #:
    #:       def configure(self):
    #:          assert self.filename
    #:
    #:   class Something(Component):
    #:
    #:       def configure(self):
    #:           self += File('nginx.conf')
    #:
    namevar = None

    #: (*readonly*) The workdir attribute is set by batou when a component
    #: before a component is configured and defaults to
    #: ``<root>/work/<componentname>``. Built-in components treat all relative
    #: destination paths as relative to the work directory.
    #:
    #: During verify() and apply() batou automatically switches the current
    #: working directory to this.
    workdir = None

    @property
    def defdir(self):
        """(*readonly*) The definition directory (where the ``component.py`` lives).

        Built-in components treat all path names of source files as relative
        to the definition directory.
        """
        return self.root.defdir

    @property
    def host(self):
        """(*readonly*) The :py:class:`Host` object this component is
        configured for."""
        return self.root.host

    @property
    def environment(self):
        """(*readonly*) The :py:class:`Environment` object this component is
        configured for."""
        return self.root.environment

    @property
    def root(self):
        """(*readonly*) The :py:class:`RootComponent` object this component is
        configured for."""
        current = self
        while isinstance(current, Component):
            current = current.parent
        return current

    #: During ``configure()`` this attribute always keeps the last added
    #: sub-component -- similar to the interactive Python interpreter
    #: keeping track of the last result. This can reduce the number of
    #: temporary names you have to assign if you want to reference a specific
    #: sub-component.
    _ = None

    changed = False
    _prepared = False

    def __init__(self, namevar=None, **kw):
        if self.namevar:
            if namevar is None:
                raise ValueError('Namevar %s required' % self.namevar)
            kw[self.namevar] = namevar
        # Can't use the attribute setter here as our special attributes will
        # error out as long as the component is not attached to a root.
        self.__dict__.update(kw)

    def __repr__(self):
        return '<%s (%s) "%s">' % (
            self.__class__.__name__,
            self.host.name,
            self._breadcrumbs)

    # Configuration phase

    def prepare(self, parent):
        self.parent = parent
        self.workdir = parent.workdir
        self.sub_components = []
        if self.parent is self.root:
            self._overrides(self.root.overrides)
        # Fix up attributes that have been set through the constructor.
        for k, v in self.__dict__.items():
            attribute = getattr(self.__class__, k, None)
            if not isinstance(attribute, Attribute):
                continue
            # Setting it using the mutator causes conversions and our
            # special attribute handling to catch up.
            setattr(self, k, v)

        self.configure()
        self += self._get_platform()
        self.__setup_event_handlers__()
        self._prepared = True

    def _overrides(self, overrides={}):
        missing = []
        for key, value in overrides.items():
            # I explicity check whether we're overriding an attribute on the
            # class. a) that's the intended semantic I want to check for and
            # b) this suppresses implicit __get__ conversions of Attribute
            # objects.
            if not hasattr(self.__class__, key):
                missing.append(key)
                continue
            setattr(self, key, value)
        if missing:
            raise batou.MissingOverrideAttributes(self, missing)

    def configure(self):
        """Configure the component by computing target state and declaring
        sub-components.

        This is the "declarative" part of batou -- consider a rather functional
        approach to implementing this.

        Perform as much preparatory computation of target state as possible
        so that batou can perform as many checks as possible before starting
        to modify target systems.

        Sub-components are added to this component by using the ``+=`` syntax:

        .. code-block:: python

            class MyComponent(Component):

                def configure(self):
                    self += File('asdf')
                    self += File('bsdf')
                    self += File('csdf')

        The order that sub-components will be worked on is given by the order
        of the ``+=`` assignments.

        .. warning::
            ``configure`` must not change state on the target systems and
            should only interact with the outside system in certain situations.
            It is not guaranteed whether this method will be called on the host
            running the master command, or on any number of the target systems.

            ``configure`` can be called by batou multiple times (with
            re-initialized attributes) for batou to automatically discover
            correct order.

            Consequently, it is wise to keep computational overhead low to
            ensure fast deployments.

        .. warning::

            Using functions from :py:module:random can cause your configuration
            to be come non-convergent and thus cause unnecessary, repeated
            updates. If you like to use a random number, make sure you seed
            the random number generator with a predictable value, that may
            be stored in the environment overrides or secrets.

        """
        pass

    # Deployment phase

    def deploy(self, predict_only=False):
        # Remember: this is a tight loop - we need to keep this code fast.

        # Reset changed flag here to support triggering deploy() multiple
        # times. This is mostly helpful for testing, but who knows.
        self.changed = False
        for sub_component in self.sub_components:
            sub_component.deploy(predict_only)
            if sub_component.changed:
                self.changed = True

        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)
        with self.chdir(self.workdir), self:
            try:
                with batou.utils.Timer(
                        '{} verify()'.format(self._breadcrumbs)):
                    try:
                        self.verify()
                    except Exception:
                        if predict_only:
                            raise batou.UpdateNeeded()
                        raise
            except batou.UpdateNeeded:
                self.__trigger_event__(
                    'before-update', predict_only=predict_only)
                output.annotate(self._breadcrumbs)
                if not predict_only:
                    self.update()
                self.changed = True

    def verify(self):
        """Verify whether this component has been deployed correctly or needs
        to be updated.

        Raise the :py:class:`batou.UpdateNeeded` exception if the desired
        target state is not reached. Use the :py:meth:`assert_*` methods (see
        below) to check for typical conditions and raise this exception
        comfortably.

        This method is run exactly once on the target system when batou
        has entered the deployment phase. The working directory is
        automatically switched to the :py:attr:`workdir`.
        """
        pass

    def update(self):
        """Update the deployment of this component.

        ``update`` is called when ``verify`` has raised the
        :py:class:UpdateNeeded exception.

        When implementing ``update`` you can assume that the target state has
        not been reached but you are not guaranteed to find a clean
        environment.  You need to take appropriate action to move whatever
        state you find to the state you want.

        We recommend two best practices to have your components be reliable,
        convergent, and fast:

        1. Create a clean temporary state before applying new state. (But be
           careful if you manage stateful things like database directories
           or running processes.)

        2. If ``update`` and ``verify`` become too complicated then split
           your component into smaller components that can implement
           the ``verify``/``update`` cycle in a simpler fashion.

           ``verify`` and ``update`` should usually not be longer than a
           few lines of code.
        """
        pass

    def last_updated(self):
        """When this component was last updated, given as a timestamp (
        seconds since epoch in local time on the system).

        You can implement this, optionally, to help other components
        that depend on this component to determine whether they should
        update themselves or not.

        """
        raise NotImplementedError

    # We're context managers - to allow components to do setup/teardown nicely.

    def __enter__(self):
        """Enter the component's context.

        Components are context managers: the context is entered before
        calling ``verify`` and left after calling ``update`` (or after
        ``verify`` if no update was needed).

        This can be used to perform potentially expensive or stateful
        setup and teardown actions, like mounting volumes.

        See Python's context manager documentation if you want to know more
        about this mechanism.
        """
        pass

    def __exit__(self, type, value, tb):
        """Exit the component's context."""
        pass

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

    def __trigger_event__(self, event, predict_only):
        # We notify all components that belong to the same root.
        for target in self.root.component.recursive_sub_components:
            for handler in target._event_handlers.get(event, []):
                if not check_event_scope(
                        handler._event['scope'], self, target):
                    continue
                if predict_only:
                    output.annotate(
                        'Trigger {}: {}.{}'.
                        format(event, handler.im_self, handler.__name__))
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
            component.prepare(self)
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
    def _add_platform(cls, name, platform):
        if '_platforms' not in cls.__dict__:
            cls._platforms = {}
        cls._platforms[name] = platform

    def _get_platform(self):
        """Return the platform component for this component if one exists."""
        platforms = self.__class__.__dict__.get('_platforms', {})
        return platforms.get(self.environment.platform, lambda: None)()

    # Resource provider/user API

    def provide(self, key, value):
        """Provide a resource.

       :param str key: They key under which the resource is provided.
       :param object value: The value of the resource.

        Resource values can be of any type. Typically you can pass around
        component objects or individual configuration values, like network
        addresses, or similar.

        """
        self.environment.resources.provide(self.root, key, value)

    def require(self, key, host=None, strict=True, reverse=False, dirty=False):
        """Require a resource.

        :param str key: The key under which the resource was provided.
        :param object host: The host object that the provided resource belongs
            to.
        :param bool strict: If true, then it is an error if no resources
            were provided given the required key.
        :param bool reverse: By default a component that requires another one
            also depends on the one that provides a resource. If ``reverse``
            is set to ``True`` then this dependency is reversed and the
            component that provides a resource depends on the component
            requiring it.
        :param bool dirty: When a component requires a resource then it will
            normally be configured again when another component is configured
            later that changes the list of resources that were required.

            Under very special circumstances it may be necessary to not
            get reconfigured when the required resource changes to break
            cycles in dependencies. **Use with highest caution** as this
            can cause your components to have incomplete configuration.
        :return: The matching list of resources that were provided.
        :rtype: list

        .. note::

            Calling ``require`` may cause an internal exception to be raised
            that you *must* not catch: batou uses this as a signal that this
            component's configuration is incomplete and keeps track of the
            desired resource key. If another component later provides this
            resource then this component's ``configure`` will be run again,
            causing ``require`` to complete successfully.

        """
        return self.environment.resources.require(
            self.root, key, host, strict, reverse, dirty)

    def require_one(self, key, host=None, strict=True, reverse=False,
                    dirty=False):
        """Require a resource, returning a scalar.

        For the parameters, see :py:meth:`require`.

        :return: The matching resource that was provided.
        :rtype: object

        This version returns a single value instead of a list. Also, if the
        number of potential results is not exactly one, then an error will
        be raised (which you should not catch). batou will notify you of this
        as being an inconsistent configuration.

        """
        resources = self.require(key, host, strict, reverse, dirty)
        if len(resources) > 1:
            raise KeyError(
                'Expected only one result, got multiple for (key={}, host={})'.
                format(key, host))
        elif len(resources) == 0:
            raise SilentConfigurationError()
        return resources[0]

    def assert_cmd(self, *args, **kw):
        """Assert that given command returns successfully, raise
        :py:class:`UpdateNeeded` otherwise.

        For details about the command arguments and what a successful execution
        means, see :py:func:`batou.component.Component.cmd`.

        """
        try:
            self.cmd(*args, **kw)
        except batou.utils.CmdExecutionError:
            raise batou.UpdateNeeded()

    def assert_file_is_current(self, reference, requirements=[], **kw):
        """Assert that the file given by the ``reference`` pathname has been
        created or updated after the given list of ``requirement`` file names,
        raise :py:class:`UpdateNeeded` otherwise.

        :param str reference: The file path you want to check for being
            current.

        :param list requirements: The list of filenames you want to check
            against.

        :param dict kw: Arguments that are passed through to
            ``last_update`` which can be used to use different time stamps
            than ``st_mtime``. See
            :py:meth:`batou.lib.file.File.last_updated` for possible values.

        :return: ``None``, if ``reference`` is as new or newer as all
            ``requirements``.

        :raises UpdateNeeded: if the reference file is older than any of the
            ``requirements``.

        """
        from batou.lib.file import BinaryFile
        reference = BinaryFile(reference)
        self |= reference
        reference.assert_component_is_current(
            [BinaryFile(r) for r in requirements], **kw)

    def assert_component_is_current(self, requirements=[], **kw):
        """Assert that this component has been updated more recently
        than the components specified in the ``requirements``,
        raise :py:class:`UpdateNeeded` otherwise.

        :param list requirements: The list of components you want to
            check against.

        :return: ``None``, if this component is as new or newer as all
            ``requirements``.

        :param dict kw: Arguments that are passed through to
            each ``last_update`` call. The semantics depend on the components'
            implementations.

        :raises UpdateNeeded: if this component is older than any of the
            ``requirements``.

        The age of a component is determined by calling ``last_updated``
        on this and each requirement component.

        """

        if isinstance(requirements, Component):
            requirements = [requirements]
        reference = self.last_updated(**kw)
        if reference is None:
            output.annotate(
                'assert_component_is_current({}, ...): No reference'.format(
                    self._breadcrumb),
                debug=True)
            raise batou.UpdateNeeded()
        for requirement in requirements:
            self |= requirement
            required = requirement.last_updated(**kw)
            if reference < required:
                output.annotate(
                    'assert_component_is_current({}, {}): {} < {}'.format(
                        self._breadcrumb, requirement._breadcrumb, reference,
                        required),
                    debug=True)
                raise batou.UpdateNeeded()

    def assert_no_subcomponent_changes(self):
        """Assert that, during this run of batou, non of this
        components' sub-components have required an update.

        :return: ``None``, if none if this components'
            sub-components have required an update during this run of batou.

        :raises UpdateNeeded: if any of this components' sub-components
            have required an update during this run of batou.

        .. note::

            Using this change indicator can be unreliable if you fail to
            perform your update correctly. It is likely that when later
            resuming an aborted deployment this change won't be triggered
            again.

        """
        for component in self.sub_components:
            if component.changed:
                raise batou.UpdateNeeded()

    def assert_no_changes(self):
        """Assert that, during this run of batou, neither
        this component nor any of its sub-components have required an update.

        :return: ``None``, if neither this component nor any of its
            sub-components have required an update during this run of batou.

        :raises UpdateNeeded: if this component or any of its sub-components
            have required an update during this run of batou.

        .. note::

            Using this change indicator can be unreliable if you fail to
            perform your update correctly. It is likely that when later
            resuming an aborted deployment this change won't be triggered
            again.

        """
        if self.changed:
            raise batou.UpdateNeeded()
        self.assert_no_subcomponent_changes()

    def cmd(self, cmd, silent=False, ignore_returncode=False,
            communicate=True, env=None, expand=True):
        """Perform a (shell) command.

        Use this to interact with the target system during ``verify``,
        ``update``, ``__enter__``, or ``__exit__``.

        .. warning::

            Do **not** use this during ``configure``.

        :param str cmd: The command you want to execute including all
            arguments. This will be parsed by the system shell, so be
            careful of quoting.

        :param bool silent: whether output should be shown in the case of
            errors.

        :param bool ignore_returncode: If true, do not raise an exception
            if the return code of the command indicates failure.

        :param bool communicate: If ``True``, call ``communicate()`` and wait
            for the process to finish, and process the return code. If
            ``False`` start the process and return the :py:class:`Popen`
            object after starting the process. You are then responsible
            for communicating, processing, and terminating the process
            yourself.

        :param bool expand: Treat the ``cmd`` as a template and process it
            through Jinja2 in the context of this component.

        :return: (stdout, stderr) if ``communicate`` is ``True``,
            otherwise the  :py:class:`Popen` process is returned.

        :raises CmdExecutionError: if return code indicated failure and
            ``ignore_returncode`` was not set.

        """
        if expand:
            cmd = self.expand(cmd)
        return batou.utils.cmd(
            cmd, silent, ignore_returncode, communicate, env)

    def map(self, path):
        """Perform a VFS mapping on the given path.

        If the environment has VFS mapping configured, compute the new path
        based on the mapping.

        Whenever you get a path name from the outside (i.e. environment
        overrides or from the constructor) or use absolute paths in your
        configuration, you should call ``map`` as early as possible during
        ``configure``. If you are using :py:class:``batou.component.Attribute``
        for constructor arguments or overrides, then you can specify ``map``
        on the attribute to avoid having to map this yourself.

        You should rely on other components to do the same, so if you pass a
        path to another component's constructor, you do not have to call
        ``map`` yourself.
        """
        path = os.path.expanduser(path)
        if not path.startswith('/'):
            return os.path.normpath(os.path.join(self.workdir, path))
        return self.environment.map(path)

    def touch(self, filename):
        """Built-in equivalent of the ``touch`` UNIX command.

        Use during ``verify``, ``update``, ``__enter__``, or ``__exit__``,
        to interact with the target system.

        .. warning::

            Do **not** use during ``configure``.

        """
        if os.path.exists(filename):
            os.utime(filename, None)
        else:
            open(filename, 'w').close()

    def expand(self, string, component=None, **kw):
        """Expand the given string in the context of this component.

        When computing configuration data, you can perform inline
        template expansions of strings. This is an alternative to Python's
        built-in string templates, to keep your inline configuration
        in sync with the external file templating based on Jinja2.

        :param unicode string: The string you want to be expanded as a Jinja2
            template.

        :param batou.component.Component component: By default this ``self``.
            To perform the template expansion in the context of another
            component you can pass it through this argument (or call the
            other component's ``expand``).

        :param dict kw: Additional keyword arguments are passed into the
            template's context as global names.

        :return: the expanded template.

        :return type: unicode

        """

        engine = batou.template.Jinja2Engine()
        args = self._template_args(component=component, **kw)
        return engine.expand(string, args, self._breadcrumbs)

    def template(self, filename, component=None):
        """Expand the given file in the context of this component.

        Instead of using the ``File`` component to expand templates, you
        can expand a file and receive a unicode string (instead of directly
        rendering the file to a target location).

        :param str filename: The file you want to expand. The filename is
            **not** mapped by this function. Map the filename before calling
            ``template`` if needed.

        :param batou.component.Component component: By default this ``self``.
            To perform the template expansion in the context of another
            component you can pass it through this argument (or call the
            other component's ``expand``).

        :param dict kw: Additional keyword arguments are passed into the
            template's context as global names.

        :return: the expanded template.

        :return type: unicode

        """
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
        """Change the working directory.

        Use this to interact with the target system during ``verify``,
        ``update``, ``__enter__``, or ``__exit__``.

        .. warning::

            Do **not** use this during ``configure``.

        The given path can be absolute or relative to the current
        working directory. No mapping is performed.

        This is a context mapper, so you can change the path temporarily
        and automatically switch back:

        .. code-block:: python

            def update(self):
                with self.chdir('/tmp'):
                    self.touch('asdf')
        """
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
        if self.parent is not self.root:
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
        if self.namevar is None:
            return None
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

    ignore = False

    def __init__(self, name, environment, host, features, ignore,
                 factory, defdir, workdir, overrides=None):
        self.name = name
        self.environment = environment
        self.host = host
        self.features = features
        self.ignore = ignore
        self.defdir = defdir
        self.workdir = workdir
        self.overrides = overrides if overrides else {}
        self.factory = factory

    def prepare(self):
        self.component = self.factory()
        if self.features:
            # Only override the default defined on the component class
            # if the environment specified anything for this component/host
            # combination.
            self.component.features = self.features
        self.component.prepare(self)

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
        if obj is None:
            # We're being accessed as a class attribute.
            return self
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
            try:
                value = self.conversion(value)
            except Exception as e:
                # Try to detect our own name.
                name = '<unknown>'
                for k in dir(obj):
                    if getattr(obj.__class__, k, None) is self:
                        name = k
                        break
                raise batou.ConversionError(
                    obj, name, value, self.conversion, e)
        self.instances[obj] = value

    def convert_literal(self, value):
        return ast.literal_eval(value)

    def convert_list(self, value):
        l = value.split(',')
        l = [x.strip() for x in l]
        l = filter(None, l)
        return l
