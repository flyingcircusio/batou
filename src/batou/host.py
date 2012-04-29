# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt
"""Host class and related code to interface with target hosts."""

from __future__ import print_function, unicode_literals
import contextlib
import fcntl
import os


def escape(path):
    """Return a safely escaped version of path.

    Implementation inspired by re.escape.
    """
    s = list(path)
    for i, c in enumerate(path):
        if c in ('\\', '"', '$'):
            s[i] = '\\' + c
    return path[:0].join(['"'] + s + ['"'])


class Host(object):
    """Deploy to an individual remote host."""

    # until we know for better, we leave service_home replacements alone
    service_home = u'${service_home}'

    def __init__(self, fqdn, environment):
        self.environment = environment
        self.fqdn = fqdn
        self.name = self.fqdn.split('.')[0]
        self.components = []

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
        with self.locked():
            for component in self.components:
                component.deploy()
