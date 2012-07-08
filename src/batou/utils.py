from __future__ import print_function
import contextlib
import fcntl
import itertools
import os
import socket
import subprocess
import sys


def input(prompt):
    print(prompt)
    sys.stdout.flush()
    return raw_input()


class MultiFile(object):

    def __init__(self, files):
        self.files = files

    def write(self, value):
        for file in self.files:
            file.write('-> '+value)

    def flush(self):
        for file in self.files:
            file.flush()

    def read(self, count=None):
        value = self.files[0].read()
        for file in self.files[1:]:
            file.write('<- '+value)
        return value


@contextlib.contextmanager
def locked(filename):
    with open(filename, 'a+') as lockfile:
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


def flatten(listOfLists):
    return list(itertools.chain.from_iterable(listOfLists))


def notify(title, description):
    try:
        subprocess.check_call(['notify-send', title, description])
    except OSError:
        pass


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
