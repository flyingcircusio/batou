# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt
"""Host class and related code to interface with target hosts."""

from fabric.api import settings, hide
from fabric.contrib.files import exists
from .component import Component, step
import fabric.api
import hashlib
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

    def __init__(self, fqdn , environment):
        self.environment = environment
        self.fqdn = fqdn
        self.name = self.fqdn.split('.')[0]
        self.components = []

    def deploy(self):
        os.umask(0o026)
        for component in self.components:
            component.deploy()
