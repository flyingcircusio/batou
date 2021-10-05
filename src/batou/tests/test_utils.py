import os
import socket
import tempfile
import threading
import unittest
from io import StringIO

import mock
import pytest

import batou
from batou.utils import (
    Address,
    CmdExecutionError,
    MultiFile,
    NetLoc,
    call_with_optional_args,
    cmd,
    flatten,
    hash,
    locked,
    notify,
    remove_nodes_without_outgoing_edges,
    resolve,
    resolve_v6,
    revert_graph,
    topological_sort,
)

RESOLVER_ERRORS = [
    '[Errno -2] Name or service not known',  # Linux
    '[Errno 8] nodename nor servname provided, or not known',  # MacOS
]


@mock.patch("socket.getaddrinfo")
def test_host_without_port_resolves(ghbn):
    ghbn.return_value = [
        (None, None, None, None, ('127.0.0.1', 0, None, None))]
    assert resolve("localhost") == "127.0.0.1"


@mock.patch("socket.getaddrinfo", side_effect=socket.gaierror("lookup failed"))
def test_resolve_v4_socket_error_returns_none(ghbn):
    with pytest.raises(socket.gaierror) as f:
        resolve("localhost", 80)
    assert "lookup failed" == str(f.value)


@mock.patch("socket.getaddrinfo", side_effect=socket.gaierror("lookup failed"))
def test_resolve_v6_raises_on_socket_error(gai):
    with pytest.raises(socket.gaierror) as f:
        resolve_v6("localhost", 22)
    assert "lookup failed" == str(f.value)


def test_resolve_override():
    ov = {"foo.example.com": "1.2.3.4"}
    assert "1.2.3.4" == resolve("foo.example.com", 80, resolve_override=ov)


def test_resolve_v6_override():
    ov = {"foo.example.com": "::27"}
    assert "::27" == resolve_v6("foo.example.com", 80, resolve_override=ov)


def test_resolve_v6_does_not_return_link_local_addresses(output, monkeypatch):
    output.enable_debug = True

    def link_local_addrinfo(*args, **kw):
        return [(None, None, None, None, ('fe80::feaa:14ff:fe8f:94ba', 80,
                                          None, None))]

    monkeypatch.setattr(socket, 'getaddrinfo', link_local_addrinfo)

    with pytest.raises(ValueError) as err:
        resolve_v6("foo.example.com", 80)
    assert 'No valid address found for `foo.example.com`.' == str(err.value)

    def link_local_addrinfo(*args, **kw):
        return [(None, None, None, None, ('fe80::feaa:14ff:fe8f:94ba', 80,
                                          None, None)),
                (None, None, None, None, ('2a02::1', 80, None, None))]

    monkeypatch.setattr(socket, 'getaddrinfo', link_local_addrinfo)

    output.backend.output = ''
    assert resolve_v6('foo.example.com', 80) == '2a02::1'

    assert """\
resolving (v6) `foo.example.com`
resolved (v6) `foo.example.com` to [(None, None, None, None, ('fe80::feaa:14ff:fe8f:94ba', 80, None, None)), (None, None, None, None, ('2a02::1', 80, None, None))]
selected (v6) foo.example.com, 2a02::1
""" == output.backend.output  # noqa: E501 line too long


def test_address_without_implicit_or_explicit_port_fails():
    with pytest.raises(ValueError):
        Address("localhost")
    Address("localhost:8080")
    Address("localhost", 8080)


def test_address_resolves_listen_address():
    address = Address("localhost:8080")
    assert "127.0.0.1:8080" == str(address.listen)
    assert "localhost:8080" == str(address.connect)


def test_address_netloc_attributes():
    address = Address("localhost:8080")
    assert "127.0.0.1" == address.listen.host
    assert "8080" == address.listen.port
    assert "localhost" == address.connect.host
    assert "8080" == address.connect.port


def test_netloc_ordering():
    address1 = NetLoc("127.0.0.5")
    address2 = NetLoc("127.0.0.5", "80")
    address3 = NetLoc("asdf")
    address4 = NetLoc("asdf", "90")
    sorted_list = sorted([address3, address2, address4, address1])
    assert [address1, address2, address3, address4] == sorted_list


def test_netloc_repr():
    assert "<NetLoc `127.0.0.5:80`>" == repr(NetLoc("127.0.0.5", "80"))
    assert "<NetLoc `127.0.0.5`>" == repr(NetLoc("127.0.0.5"))


def test_address_ordering():
    address1 = Address("127.0.0.5:8080")
    address2 = Address("localhost:8080")
    address3 = Address("127.10.1.5:8080")
    address4 = Address("127.122.122.133:8080")
    sorted_list = sorted([address1, address2, address3, address4])
    assert [address1, address3, address4, address2] == sorted_list


def test_address_neither_v4_v6_invalid():
    with pytest.raises(ValueError) as f:
        Address("asdf", require_v4=False, require_v6=False)
    assert ("At least one of `require_v4` or `require_v6` is required. "
            "None were selected." == str(f.value))


def test_address_v6_only(monkeypatch):
    hostname = 'v6only.example.com'

    from batou.utils import resolve_v6_override
    monkeypatch.setitem(resolve_v6_override, hostname, '::346')

    with pytest.raises(socket.gaierror) as f:
        Address(hostname, 1234)
    assert str(f.value) in RESOLVER_ERRORS

    with pytest.raises(socket.gaierror) as f:
        Address(hostname, 1234, require_v6=True)
    assert str(f.value) in RESOLVER_ERRORS

    address = Address(hostname, 1234, require_v4=False, require_v6=True)
    assert address.listen_v6.host == "::346"


def test_address_fails_when_name_cannot_be_looked_up_at_all():
    with pytest.raises(socket.gaierror) as f:
        Address("does-not-exist.example.com:1234")
    assert str(f.value) in RESOLVER_ERRORS

    with pytest.raises(socket.gaierror) as f:
        Address(
            "does-not-exist.example.com:1234",
            require_v4=False,
            require_v6=True)
    assert str(f.value) in RESOLVER_ERRORS

    with pytest.raises(socket.gaierror) as f:
        Address(
            "does-not-exist.example.com:1234",
            require_v4=True,
            require_v6=True)
    assert str(f.value) in RESOLVER_ERRORS


def test_address_format_with_port():
    assert str(Address("127.0.0.1:8080").listen) == "127.0.0.1:8080"


@mock.patch("socket.getaddrinfo")
def test_address_should_contain_v6_address_if_available(gai):
    gai.return_value = [(None, None, None, None, ("::1", None, None, None))]
    address = Address("localhost:8080", require_v6=True)
    assert address.listen_v6.host == "::1"


def test_address_prevents_access_to_unconfigured_IPv4_netloc():
    """It raises an exception if IPv4 is not configured but accessed."""
    address = Address("localhost", 22, require_v4=False, require_v6=True)
    with pytest.raises(batou.IPAddressConfigurationError) as err:
        address.listen
    assert ('Trying to access address family IPv4 which is not configured for'
            ' localhost:22.' == str(err.value))


def test_address_prevents_access_to_unconfigured_IPv6_netloc():
    """It raises an exception if IPv6 is not configured but accessed."""
    address = Address("localhost", 22, require_v4=True, require_v6=False)
    with pytest.raises(batou.IPAddressConfigurationError) as err:
        address.listen_v6
    assert ('Trying to access address family IPv6 which is not configured for'
            ' localhost:22.' == str(err.value))


def test_netloc_str_should_brace_ipv6_addresses():
    assert "[::1]:80" == str(NetLoc("::1", 80))


def test_netloc_format_without_port():
    assert str(NetLoc("127.0.0.1")) == "127.0.0.1"


def test_flatten():
    assert [1, 2, 3, 4] == flatten([[1, 2], [3, 4]])


class MultiFileTests(unittest.TestCase):

    def test_write_and_flush_propation(self):
        file1 = StringIO()
        file2 = StringIO()
        multi = MultiFile([file1, file2])
        multi.write("asdf")
        multi.flush()
        self.assertEqual("asdf", file1.getvalue())
        self.assertEqual("asdf", file2.getvalue())


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
        list(map(os.unlink, self.files))

    def tempfile(self):
        f = tempfile.mktemp()
        self.files.append(f)
        return f

    def test_lock_creates_file_and_writes_and_removes_pid(self):
        lockfile = self.tempfile()
        with locked(lockfile):
            with open(lockfile, "r") as f:
                pid = f.read().strip()
            self.assertEqual(os.getpid(), int(pid))
        with open(lockfile, "r") as f:
            self.assertEqual("", f.read())

    def test_lock_works_with_existing_file(self):
        lockfile = self.tempfile()
        f = open(lockfile, "w")
        f.write("sadf")
        f.close()
        with locked(lockfile):
            with open(lockfile, "r") as f:
                pid = f.read().strip()
            self.assertEqual(os.getpid(), int(pid))
        with open(lockfile, "r") as f:
            self.assertEqual("", f.read())

    @mock.patch("fcntl.lockf", side_effect=fake_lock)
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

    @mock.patch("subprocess.check_call", side_effect=OSError)
    def test_notify_does_not_fail_if_os_call_fails(self, call):
        notify("foo", "bar")


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
    graph = {1: [1], 2: []}
    remove_nodes_without_outgoing_edges(graph)
    assert graph == {1: [1]}


class Checksum(unittest.TestCase):

    fixture = os.path.join(
        os.path.dirname(__file__), "fixture", "component", "haproxy.cfg")

    def test_hash_md5(self):
        self.assertEqual("ce0324fa445475e76182c0d114615c7b",
                         hash(self.fixture, "md5"))

    def test_hash_sha1(self):
        self.assertEqual(
            "164d8815aa839cca339e38054622b58ca80124a1",
            hash(self.fixture, "sha1"),
        )


@mock.patch("subprocess.Popen")
def test_cmd_joins_list_args(popen):
    popen().communicate.return_value = (b"", b"")
    popen().returncode = 0
    cmd(["cat", "foo", "bar"])
    assert popen.call_args[0] == ("cat foo bar", )


@mock.patch("subprocess.Popen")
def test_cmd_quotes_spacey_args(popen):
    popen().communicate.return_value = (b"", b"")
    popen().returncode = 0
    cmd(["cat", "foo", "bar bz baz"])
    assert popen.call_args[0] == ("cat foo 'bar bz baz'", )
    cmd(["cat", "foo", "bar 'bz baz"])
    assert popen.call_args[0] == (r"cat foo 'bar \'bz baz'", )


@mock.patch("subprocess.Popen")
def test_cmd_ignores_specified_returncodes(popen):
    popen.return_value.returncode = 4
    popen.return_value.communicate.return_value = b"", b""
    with pytest.raises(CmdExecutionError):
        cmd("asdf")
    cmd("asdf", acceptable_returncodes=[0, 4])


@mock.patch("subprocess.Popen")
def test_cmd_returns_process_if_no_communicate(popen):
    process = mock.Mock()
    popen.return_value = process
    p = cmd(["asdf"], communicate=False)
    assert popen.communicate.call_count == 0
    assert p is process


def test_call_with_optional_args():

    def foo():
        return 1

    def bar(x):
        return x

    def baz(**kw):
        return kw["x"]

    def quux(x, y):
        return x

    # The function doesn't expect x, but we're happy to call it.
    assert call_with_optional_args(foo, x=1)
    # The function expect x and it gets passed through
    assert call_with_optional_args(bar, x=4) == 4
    # The function accepts kw args and sees x
    assert call_with_optional_args(baz, x=3) == 3
    # The function accepts x but also expects y and thus breaks
    with pytest.raises(TypeError):
        call_with_optional_args(quux, x=1)
