# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt
"""Host class and related code to interface with target hosts."""

from __future__ import print_function, unicode_literals
import contextlib
import fcntl
import os


class Host(object):
    """Deploy to an individual remote host."""

    # until we know for better, we leave service_home replacements alone
    service_home = u'${service_home}'

    def __init__(self, fqdn, environment):
        self.environment = environment
        self.fqdn = fqdn
        self.name = self.fqdn.split('.')[0]
        self.components = []

    def add_component(self, name, features=None):
        """Register a top-level component as defined in the service
        for this host.
        """
        root_factory = self.environment.service.components[name]
        root = root_factory(self.environment.service, self.environment, self, features, {})
        self.components.append(root)

    @contextlib.contextmanager
    def locked(self):
        with open('.batou-lock', 'a+') as lockfile:
            try:
                fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                raise RuntimeError(
                    'cannot create lock "%s": more than one instance running '
                    'concurrently?' % lockfile, lockfile)
            # publishing the process id comes handy for debugging
            lockfile.seek(0)
            lockfile.truncate()
            print(os.getpid(), file=lockfile)
            lockfile.flush()
            yield
            lockfile.seek(0)
            lockfile.truncate()

    def deploy(self):
        os.umask(0o026)
        with self.locked():
            for component in self.components:
                component.deploy()
