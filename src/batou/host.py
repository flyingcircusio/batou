# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt
"""Manage service components for individual hosts."""

from __future__ import print_function, unicode_literals
import contextlib
import fcntl
import os


class Host(object):
    """Description of service components for a host."""

    def __init__(self, fqdn, environment):
        self.environment = environment
        self.fqdn = fqdn
        self.name = self.fqdn.split('.')[0]
        self.components = []

    # XXX this method is a smell for refactoring
    def add_component(self, name, features=None):
        """Register a top-level component as defined in the service
        for this host.
        """
        root_factory = self.environment.service.components[name]
        root = root_factory(self.environment.service, self.environment, self, features, {})
        self.components.append(root)

    # XXX This will probably go away once the external loop gets tighter control
    # about the ordering of which component gets deployed at what time.
    def deploy(self):
        """Deploy all components that belong to this host."""
        for component in self.components:
            component.deploy()
