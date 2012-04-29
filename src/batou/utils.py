# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
import socket
import os
import subprocess
import urlparse


def string_list(config_value):
    """Explode comma-separated config value."""
    config_value = config_value.strip()
    if not config_value:
        return []
    return [x.strip() for x in config_value.split(',')]


def convert_type(value, datatype):
    """Allow str, int, float, and bool values in config files."""
    if datatype == 'str':
        return str(value)
    if datatype == 'int':
        return int(value)
    if datatype == 'float':
        return float(value)
    if datatype == 'bool':
        if value.lower() in ('false', 'no', 'n', 'off'):
            return False
        return bool(value)
    if datatype == 'list':
        return string_list(value)
    raise ValueError('unknown data type', datatype)


def check_shared_object(sopath):
    """Return True is shared object is link-consistent."""
    if not os.path.exists(sopath):
        return False
    deps = subprocess.check_output(['ldd', sopath])
    return '=> not found' not in deps


def prepend_env(envvar, string):
    """Put a `string` in front of a PATH-like `envvar`.

    The elements of the `envvar` are assumed to be colon-separated. If the
    `envvar` does not exist before, it is created just with `string`.
    """
    try:
        if string not in os.environ[envvar]:
            os.environ[envvar] = '%s:%s' % (string, os.environ[envvar])
    except KeyError:
        os.environ[envvar] = string


def host_from_uri(uri):
    """Extract host part from URI."""
    host = urlparse.urlsplit(uri).netloc
    host = host.split(':')[0]
    if '@' in host:
        host = host.split('@')[1]
    return host


def resolve(address):
    if ':' in address:
        host, port = address.split(':')
    else:
        host, port = address, None
    try:
        address = socket.gethostbyname(host)
    except socket.gaierror as e:
        raise socket.gaierror('%s (%s)' % (str(e), host))
    if port:
        address += ':%s' % port
    return address


class Address(object):
    """An internet service address that can be listened and connected to.

    The expected constructor address is expected to be the address that can be
    connected to. The listen address will be computed automatically.

    """

    def __init__(self, connect_address, port=None):
        if ':' in connect_address:
            connect, port = connect_address.split(':')
        else:
            connect = connect_address
        listen = resolve(connect)
        self.listen = NetLoc(listen, str(port))
        self.connect = NetLoc(connect, str(port))


class NetLoc(object):

    def __init__(self, host, port=None):
        self.host = host
        self.port = port

    def __str__(self):
        result = self.host
        if self.port:
            result += ':' + self.port
        return result


class Hook(object):
    pass
