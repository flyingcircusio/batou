# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
import socket
import os
import subprocess
import urlparse


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

    The constructor address is expected to be the address that can be
    connected to. The listen address will be computed automatically.

    """

    def __init__(self, connect_address, port=None):
        if ':' in connect_address:
            connect, port = connect_address.split(':')
        else:
            connect = connect_address
        self.connect = NetLoc(connect, str(port))
        self.listen = NetLoc(resolve(connect), str(port))


class NetLoc(object):
    """A network location specified by host and port."""

    def __init__(self, host, port=None):
        self.host = host
        self.port = port

    def __str__(self):
        result = self.host
        if self.port:
            result += ':' + self.port
        return result
