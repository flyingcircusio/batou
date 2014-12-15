from collections import defaultdict
import contextlib
import fcntl
import hashlib
import itertools
import logging
import os
import socket
import subprocess
import sys
import time


logger = logging.getLogger(__name__)


class MultiFile(object):

    def __init__(self, files):
        self.files = files

    def write(self, value):
        for file in self.files:
            file.write(value)

    def flush(self):
        for file in self.files:
            file.flush()


@contextlib.contextmanager
def locked(filename):
    # XXX can we make this not leave files around?
    with open(filename, 'a+') as lockfile:
        try:
            fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            print >> sys.stderr, 'Could not acquire lock {}'.format(filename)
            raise RuntimeError(
                'cannot create lock "%s": more than one instance running '
                'concurrently?' % lockfile, lockfile)
        # publishing the process id comes handy for debugging
        lockfile.seek(0)
        lockfile.truncate()
        print >> lockfile, os.getpid()
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
        if port is None:
            raise ValueError('Need port for service address.')
        self.connect = NetLoc(connect, str(port))
        self.listen = NetLoc(resolve(connect), str(port))

    def __str__(self):
        return str(self.connect)


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


def revert_graph(graph):
    graph = ensure_graph_data(graph)
    reverse_graph = defaultdict(set)
    for node, dependencies in graph.items():
        # Ensure all nodes will exist
        reverse_graph[node]
        for dependency in dependencies:
            reverse_graph[dependency].add(node)
    return reverse_graph


def ensure_graph_data(graph):
    # Ensure that all nodes exist as keys even if they don't have outgoing
    # relations.
    for node, relations in list(graph.items()):
        for relation in relations:
            if relation not in graph:
                graph[relation] = set()
    return graph


class CycleError(ValueError):
    """Graph contains at least one cycle."""

    def __str__(self):
        message = []
        components = self.args[0].items()
        components.sort(key=lambda x: x[0].name)
        for component, subs in components:
            message.append('    '+component.name)
            for sub in subs:
                message.append('        '+sub.name)
        return '\n'+'\n'.join(message)


def remove_nodes_without_outgoing_edges(graph):
    for node, dependencies in list(graph.items()):
        if not dependencies:
            del graph[node]


def topological_sort(graph):
    """Take a directed graph and provide a topological sort of all nodes.

    The graph is given as

    {node: [dependency, dependency], ...}

    If the graph has cycles a ValueError will be raised.
    """
    graph = ensure_graph_data(graph)
    sorted = []
    reverse_graph = revert_graph(graph)
    roots = [node for node, incoming in reverse_graph.items()
             if not incoming]
    while roots:
        root = roots.pop()
        sorted.append(root)
        for node in list(graph[root]):
            graph[root].remove(node)
            reverse_graph[node].remove(root)
            if not reverse_graph[node]:
                roots.append(node)
    if any(graph.values()):
        # Simplify the graph a bit to make it easier to spot the cycle.
        remove_nodes_without_outgoing_edges(graph)
        raise CycleError(dict(graph))
    return sorted


class CmdExecutionError(RuntimeError):
    pass


def cmd(cmd, silent=False, ignore_returncode=False, communicate=True,
        env=None, acceptable_returncodes=[0]):
    if not isinstance(cmd, basestring):
        # We use `shell=True`, so the command needs to be a single string and
        # we need to pay attention to shell quoting.
        quoted_args = []
        for arg in cmd:
            arg = arg.replace('\'', '\\\'')
            if ' ' in arg:
                arg = "'{}'".format(arg)
            quoted_args.append(arg)
        cmd = ' '.join(quoted_args)
    if env is not None:
        add_to_env = env
        env = os.environ.copy()
        env.update(add_to_env)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        shell=True,
        env=env)
    if not communicate:
        # XXX See #12550
        return process
    stdout, stderr = process.communicate()
    if process.returncode not in acceptable_returncodes:
        if not silent:
            print("$ {}".format(cmd))
            print("STDOUT")
            print("=" * 72)
            print(stdout)
            print("STDERR")
            print("=" * 72)
            print(stderr)
        if not ignore_returncode:
            raise CmdExecutionError(
                'Command "{}" returned unsuccessfully.'.format(cmd),
                process.returncode, stdout, stderr)
    return stdout, stderr


class Timer(object):

    def __init__(self, note):
        self.duration = 0
        self.note = note

    def __enter__(self):
        self.started = time.time()

    def __exit__(self, exc1, exc2, exc3):
        self.duration = time.time() - self.started
        logger.debug(self.note + ' took %fs' % self.duration)


def hash(path, function='md5'):
    h = getattr(hashlib, function)()
    for line in open(path):
        h.update(line)
    return h.hexdigest()
