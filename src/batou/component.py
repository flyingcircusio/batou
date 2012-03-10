# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.template import TemplateEngine
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
    for name, candidate in l.items():
        if isinstance(candidate, Component):
            candidate.name = name
            candidate.defdir = defdir
            yield candidate, name
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

    def __init__(self):
        self.resources = []

    def __add__(self, resource):
        self.resources.append(resource)
        return self

    def bind(self, host):
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        clone.host = host
        clone.service = host.environment.service
        return clone

    @property
    def compdir(self):
        return '%s/work/%s' % (self.service.base, self.name)

    def _update_compdir(self):
        if not os.path.exists(self.compdir):
            os.makedirs(self.compdir)

    def deploy(self):
        """Run all methods annotated with @step(n) in sequence."""
        logger.info('deploy: %s' % self.name)
        self._update_compdir()
        os.chdir(self.compdir)
        for resource in self.resources:
            logger.info('resource: %s' % resource.id)
            resource.prepare(env=dict(host=self.host, component=self))
            resource.commit()
