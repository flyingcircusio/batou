# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.template import TemplateEngine
import batou
import batou.utils
import contextlib
import filecmp
import logging
import os
import os.path
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)


def load_components_from_file(filename):
    g = l = {}
    g.update(globals())
    oldcwd = os.getcwd()
    defdir = os.path.dirname(filename)
    os.chdir(defdir)
    execfile(filename, g, l)
    for candidate in l.values():
        if candidate in globals().values():
            # Ignore anything we pushed into the globals before execution
            continue
        if (isinstance(candidate, type) and
            issubclass(candidate, Component)):
            candidate.defdir = defdir
            candidate.name = candidate.__name__.lower()
            yield candidate
    os.chdir(oldcwd)


def subscribe(self, required_name):
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


class Component(object):

    namevar = ''

    def __init__(self, namevar=namevar, **kw):
        if self.namevar:
            kw[self.namevar] = namevar
        self.__dict__.update(kw)
        self.hooks = {}
        self.sub_components = []

    def prepare(self, service, environment, host, root, parent=None):
        self.service = service
        self.environment = environment
        self.host = host
        self.root = root
        self.parent = parent
        self.configure()
        for sub_component in self.sub_components:
            sub_component.prepare(service, environment, host, root, self)

    def configure(self):
        # May be implemented by sub components
        pass

    def verify(self):
        pass

    def update(self):
        pass

    def __add__(self, component):
        self.sub_components.append(component)
        return self

    def deploy(self):
        for sub_component in self.sub_components:
            sub_component.deploy()
        try:
            self.verify()
        except batou.UpdateNeeded:
            logger.debug('Updating {}'.format(self.breadcrumbs))
            self.update()

    @property
    def breadcrumbs(self):
        result = ''
        if self.parent is not None:
            result += self.parent.breadcrumbs + '/'
        result += self.breadcrumb
        return result

    @property
    def breadcrumb(self):
        result = self.__class__.__name__
        name = getattr(self, self.namevar, None)
        if name:
            result += ':' + name
        return result

    # Helper functions

    def assert_file_is_current(self, result, requirements=[]):
        if not os.path.exists(result):
            raise batou.UpdateNeeded()
        current = os.stat(result).st_mtime
        for requirement in requirements:
            if current < os.stat(requirement).st_mtime:
                raise batou.UpdateNeeded()

    def cmd(self, cmd):
        return subprocess.check_output([cmd], shell=True)

    def touch(self, filename):
        open(filename, 'wa').close()

    def template(self, component, filename):
        engine = batou.template.MakoEngine()
        return engine.template(filename,
                               dict(component=component,
                                    host=self.host))

    @contextlib.contextmanager
    def chdir(self, path):
        old = os.getcwd()
        os.chdir(path)
        yield
        os.chdir(old)

    def find_hooks(self, expression, host):
        hooks = []
        components = []
        for host in self.environment.hosts.values():
            for root in host.components:
                components.append(root.component)
        while components:
            current = components.pop()
            components.extend(current.sub_components)
            if expression in current.hooks:
                hooks.append(current.hooks[expression])
        return hooks


class RootComponent(object):
    """Wrapper to manage root components.

    It has a name and owns the working directory for it's component.
    """

    def __init__(self, name, component):
        self.component = component
        self.name = name

    @property
    def compdir(self):
        return '%s/work/%s' % (self.component.service.base, self.name)

    @property
    def defdir(self):
        # Awkward indirection as the defdir is annotated on the factories of
        # the top level components.
        return self.component.defdir

    def _update_compdir(self):
        if not os.path.exists(self.compdir):
            os.makedirs(self.compdir)

    def deploy(self):
        self._update_compdir()
        os.chdir(self.compdir)
        self.component.deploy()
