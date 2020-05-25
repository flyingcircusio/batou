from batou import output, DeploymentError
from collections import defaultdict
import contextlib
import fcntl
import hashlib
import itertools
import os
import pkg_resources
import socket
import subprocess
import sys
import time
import inspect


def self_id():
    template = 'batou/{version} ({python}, {system})'
    system = os.uname()
    system = ' '.join([system[0], system[2], system[4]])
    version = pkg_resources.require("batou")[0].version
    python = sys.implementation.name
    python += ' {0}.{1}.{2}-{3}{4}'.format(*sys.version_info)
    return template.format(**locals())


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
            print('Could not acquire lock {}'.format(filename),
                  file=sys.stderr)
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


def flatten(list_of_lists):
    return list(itertools.chain.from_iterable(list_of_lists))


def notify_send(title, description):
    subprocess.call(['notify-send', title, description])


def notify_macosx(title, description):
    subprocess.call([
        'osascript', '-e',
        'display notification "{}" with title "{}"'.format(
            description, title)])


def notify_none(title, description):
    pass


try:
    subprocess.check_output(
        ['which', 'osascript'], stderr=subprocess.STDOUT)
    notify = notify_macosx
except (subprocess.CalledProcessError, OSError):
    try:
        subprocess.check_output(
            ['which', 'notify-send'], stderr=subprocess.STDOUT)
        notify = notify_send
    except (subprocess.CalledProcessError, OSError):
        notify = notify_none


resolve_override = {}
resolve_v6_override = {}


def resolve(host, resolve_override=resolve_override):
    address = resolve_override.get(host)
    if not address:
        try:
            address = socket.gethostbyname(host)
        except socket.gaierror:
            return None
    return address


def resolve_v6(host, port, resolve_override=resolve_v6_override):
    address = resolve_override.get(host)
    if not address:
        try:
            address = socket.getaddrinfo(
                host, int(port),
                socket.AF_INET6)[0][4][0]
        except socket.gaierror:
            address = None
    if address and address.startswith('fe80:'):
        # Don't hand out link-local addresses. This happes with
        # vagrant, and does not help as services cannot bind those
        # addresses without additional configuration, i.e. the
        # interface.
        address = None
    return address


class Address(object):
    """An internet service address that can be listened and connected to.

    The constructor address is expected to be the address that can be
    connected to. The listen address will be computed automatically.

    .. code-block:: pycon

        >>> x = Address('localhost', 80)
        >>> str(x.connect)
        'localhost:80'
        >>> str(x.listen)
        '127.0.0.1:80'

    """

    #: The connect address as it should be used when configuring clients.
    #: This is a :py:class:`batou.utils.NetLoc` object.
    connect = None

    #: The listen (or bind) address as it should be used when configuring
    #: servers. This is a :py:class:`batou.utils.NetLoc` object.
    listen = None

    #: The IPv6 listen (or bind) address as it should be used when configuring
    #: servers. This is a :py:class:`batou.utils.NetLoc` object or None, if
    #: there is no IPv6 address.
    listen_v6 = None

    def __init__(self, connect_address, port=None):
        if ':' in connect_address:
            connect, port = connect_address.split(':')
        else:
            connect = connect_address
        if port is None:
            raise ValueError('Need port for service address.')
        self.connect = NetLoc(connect, str(port))
        v4_address = resolve(connect)
        if v4_address:
            self.listen = NetLoc(v4_address, str(port))
        v6_address = resolve_v6(connect, port)
        if v6_address:
            self.listen_v6 = NetLoc(v6_address, str(port))

        if not self.listen and not self.listen_v6:
            raise socket.gaierror(
                "No IPv4 or IPv6 address for {!r}".format(connect))

    def __lt__(self, other):
        if isinstance(other, Address):
            return str(self) < str(other)
        return NotImplemented

    def __str__(self):
        return str(self.connect)


class NetLoc(object):
    """A network location specified by host and port.

    Network locations can automatically render an appropriate string
    representation:

    .. code-block:: pycon

        >>> x = NetLoc('127.0.0.1')
        >>> x.host
        '127.0.0.1'
        >>> x.port
        None
        >>> str(x)
        '127.0.0.1'

        >>> y = NetLoc('127.0.0.1', 80)
        >>> str(y)
        '127.0.0.1:80'

    """

    #: The host part of this network location. Can be a hostname or IP address.
    host = None
    #: The port of this network location. Can be ``None`` or an integer.
    port = None

    def __init__(self, host, port=None):
        self.host = host
        self.port = port

    def __str__(self):
        if self.port:
            if ':' in self.host:  # ipv6
                fmt = '[{self.host}]:{self.port}'
            else:
                fmt = '{self.host}:{self.port}'
        else:
            fmt = '{self.host}'
        return fmt.format(self=self)


def revert_graph(graph):
    graph = ensure_graph_data(graph)
    reverse_graph = defaultdict(set)
    for node, dependencies in list(graph.items()):
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

    def __str__(self):
        message = []
        components = list(self.args[0].items())
        components.sort(key=lambda x: x[0].name)
        for component, subs in components:
            message.append(component.name + ' depends on')
            for sub in subs:
                message.append('        ' + sub.name)
        return '\n'.join(message)


def remove_nodes_without_outgoing_edges(graph):
    for node, dependencies in list(graph.items()):
        if not dependencies:
            del graph[node]


def topological_sort(graph):
    # Take a directed graph and provide a topological sort of all nodes.
    #
    # The graph is given as
    #
    # {node: [dependency, dependency], ...}
    #
    # If the graph has cycles a CycleError will be raised.

    graph = ensure_graph_data(graph)
    sorted = []
    reverse_graph = revert_graph(graph)
    roots = [node for node, incoming in list(reverse_graph.items())
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


class CmdExecutionError(DeploymentError, RuntimeError):

    def __init__(self, cmd, returncode, stdout, stderr):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.args = (cmd, returncode, stdout, stderr)

    def report(self):
        output.error(self.cmd)
        output.tabular("Return code", str(self.returncode), red=True)
        output.line('STDOUT', red=True)
        output.annotate(self.stdout)
        output.line('STDERR', red=True)
        output.annotate(self.stderr)


def cmd(cmd, silent=False, ignore_returncode=False, communicate=True,
        env=None, acceptable_returncodes=[0], encoding='utf-8'):
    if not isinstance(cmd, str):
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
    output.annotate('cmd: {}'.format(cmd), debug=True)
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
    if encoding is not None:
        stdout = stdout.decode(encoding, errors='replace')
        stderr = stderr.decode(encoding, errors='replace')
    if process.returncode not in acceptable_returncodes:
        if not ignore_returncode:
            raise CmdExecutionError(
                cmd, process.returncode, stdout, stderr)
    return stdout, stderr


class Timer(object):

    def __init__(self, note):
        self.duration = 0
        self.note = note

    def __enter__(self):
        self.started = time.time()

    def __exit__(self, exc1, exc2, exc3):
        self.duration = time.time() - self.started
        output.annotate(self.note + ' took %fs' % self.duration, debug=True)


def hash(path, function='sha_512'):
    h = getattr(hashlib, function)()
    with open(path, 'rb') as f:
        chunk = f.read(64*1024)
        while chunk:
            h.update(chunk)
            chunk = f.read(64*1024)
    return h.hexdigest()


def call_with_optional_args(func, **kw):
    """Provide a way to perform backwards-compatible call,
    passing only arguments that the function actually expects.
    """
    call_kw = {}
    verify_args = inspect.signature(func)
    for name, parameter in verify_args.parameters.items():
        if name in kw:
            call_kw[name] = kw[name]
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            call_kw = kw
            break
    return func(**call_kw)
