from batou.utils import hash, CmdExecutionError
from batou.utils import remove_nodes_without_outgoing_edges, cmd
from batou.utils import resolve, MultiFile, locked, notify, Address
from batou.utils import revert_graph, topological_sort, flatten, NetLoc
from StringIO import StringIO
import mock
import os
import pytest
import socket
import tempfile
import threading
import unittest


@mock.patch('socket.gethostbyname')
def test_host_without_port_resolves(ghbn):
    ghbn.return_value = '127.0.0.1'
    assert resolve('localhost') == '127.0.0.1'


@mock.patch('socket.gethostbyname')
def test_host_with_port_resolves_and_keeps_port(ghbn):
    ghbn.return_value = '127.0.0.1'
    assert resolve('localhost:8080') == '127.0.0.1:8080'


@mock.patch('socket.gethostbyname',
            side_effect=socket.gaierror('lookup failed'))
def test_socket_error_shows_hostname(ghbn):
    with pytest.raises(socket.gaierror) as e:
        resolve('localhost')
    assert str(e.value) == 'lookup failed (localhost)'


def test_flatten():
    assert [1, 2, 3, 4] == flatten([[1, 2], [3, 4]])


class MultiFileTests(unittest.TestCase):

    def test_write_and_flush_propation(self):
        file1 = StringIO()
        file2 = StringIO()
        multi = MultiFile([file1, file2])
        multi.write('asdf')
        multi.flush()
        self.assertEquals('asdf', file1.getvalue())
        self.assertEquals('asdf', file2.getvalue())


the_fake_lock = threading.Lock()


def fake_lock(lockfile, options):
    # Emulate fcntl's behaviour if we would be two processes.
    success = the_fake_lock.acquire(False)
    if not success:
        raise IOError


class LockfileContextManagerTests(unittest.TestCase):

    def setUp(self):
        self.files = []

    def tearDown(self):
        map(os.unlink, self.files)

    def tempfile(self):
        f = tempfile.mktemp()
        self.files.append(f)
        return f

    def test_lock_creates_file_and_writes_and_removes_pid(self):
        lockfile = self.tempfile()
        with locked(lockfile):
            pid = open(lockfile, 'r').read().strip()
            self.assertEquals(os.getpid(), int(pid))
        self.assertEquals('', open(lockfile, 'r').read())

    def test_lock_works_with_existing_file(self):
        lockfile = self.tempfile()
        f = open(lockfile, 'w')
        f.write('sadf')
        f.close()
        with locked(lockfile):
            pid = open(lockfile, 'r').read().strip()
            self.assertEquals(os.getpid(), int(pid))
        self.assertEquals('', open(lockfile, 'r').read())

    @mock.patch('fcntl.lockf', side_effect=fake_lock)
    def test_lock_cant_lock_twice(self, lockf):
        lockfile = self.tempfile()
        with locked(lockfile):
            locked2 = locked(lockfile)
            self.assertRaises(RuntimeError, locked2.__enter__)


class NotifyTests(unittest.TestCase):

    # XXX: What this actually should test is:
    # if notify-send is there, use it. It does not need to exit on all
    # non-darwin machines.
    # @pytest.mark.skipif("sys.platform == 'darwin'")
    # @mock.patch('subprocess.check_call')
    # def test_notify_calls_notify_send(self, call):
    #     notify('foo', 'bar')
    #     call.assert_called_with(['notify-send', 'foo', 'bar'])

    @mock.patch('subprocess.check_call', side_effect=OSError)
    def test_notify_does_not_fail_if_os_call_fails(self, call):
        notify('foo', 'bar')


class AddressNetLocTests(unittest.TestCase):

    def test_address_without_implicit_or_explicit_port_fails(self):
        self.assertRaises(ValueError, Address, 'localhost')
        Address('localhost:8080')
        Address('localhost', 8080)

    def test_address_resolves_listen_address(self):
        address = Address('localhost:8080')
        self.assertEquals('127.0.0.1:8080', str(address.listen))
        self.assertEquals('localhost:8080', str(address.connect))

    def test_address_netloc_attributes(self):
        address = Address('localhost:8080')
        self.assertEquals('127.0.0.1', address.listen.host)
        self.assertEquals('8080', address.listen.port)
        self.assertEquals('localhost', address.connect.host)
        self.assertEquals('8080', address.connect.port)


def test_address_format_with_port():
    assert str(Address('127.0.0.1:8080').listen) == '127.0.0.1:8080'


def test_netloc_format_without_port():
    assert str(NetLoc('127.0.0.1')) == '127.0.0.1'


def test_revert_graph_no_edges_is_identical():
    graph = {1: set(), 2: set()}
    assert graph == dict(revert_graph(graph))


def test_revert_graph_one_edge_reverses():
    graph = {1: set([2])}
    assert {2: set([1]), 1: set()} == dict(revert_graph(graph))


def test_topological_sort_simple_chain():
    graph = {1: set([2]), 2: set([3]), 3: set([4])}
    assert [1, 2, 3, 4] == topological_sort(graph)


def test_topological_sort_multiple_paths():
    graph = {1: set([2, 3]), 2: set([3])}
    assert [1, 2, 3] == topological_sort(graph)


def test_topological_sort_raises_on_loop():
    graph = {1: set([2]), 2: set([3]), 3: set([1])}
    with pytest.raises(ValueError):
        topological_sort(graph)


def test_topological_sort_with_single_item():
    graph = {1: set()}
    assert [1] == topological_sort(graph)


def test_graph_remove_leafs():
    graph = {1: [1],
             2: []}
    remove_nodes_without_outgoing_edges(graph)
    assert graph == {1: [1]}


class Checksum(unittest.TestCase):

    fixture = os.path.join(
        os.path.dirname(__file__), 'fixture', 'component', 'haproxy.cfg')

    def test_hash_md5(self):
        self.assertEquals('ce0324fa445475e76182c0d114615c7b',
                          hash(self.fixture, 'md5'))

    def test_hash_sha1(self):
        self.assertEquals('164d8815aa839cca339e38054622b58ca80124a1',
                          hash(self.fixture, 'sha1'))


@mock.patch('subprocess.Popen')
def test_cmd_joins_list_args(popen):
    popen().communicate.return_value = ('', '')
    popen().returncode = 0
    cmd(['cat', 'foo', 'bar'])
    assert popen.call_args[0] == ('cat foo bar',)


@mock.patch('subprocess.Popen')
def test_cmd_quotes_spacey_args(popen):
    popen().communicate.return_value = ('', '')
    popen().returncode = 0
    cmd(['cat', 'foo', 'bar bz baz'])
    assert popen.call_args[0] == ("cat foo 'bar bz baz'",)
    cmd(['cat', 'foo', "bar 'bz baz"])
    assert popen.call_args[0] == (r"cat foo 'bar \'bz baz'",)


@mock.patch('subprocess.Popen')
def test_cmd_ignores_specified_returncodes(popen):
    popen.return_value.returncode = 4
    popen.return_value.communicate.return_value = '', ''
    with pytest.raises(CmdExecutionError):
        cmd('asdf')
    cmd('asdf', acceptable_returncodes=[0, 4])


@mock.patch('subprocess.Popen')
def test_cmd_returns_process_if_no_communicate(popen):
    process = mock.Mock()
    popen.return_value = process
    p = cmd(['asdf'], communicate=False)
    assert popen.communicate.call_count == 0
    assert p is process
