from StringIO import StringIO
from batou.utils import resolve, input, MultiFile, locked, notify, Address
import mock
import os
import socket
import tempfile
import threading
import unittest


class ResolveTests(unittest.TestCase):

    @mock.patch('socket.gethostbyname')
    def test_host_without_port_resolves(self, ghbn):
        ghbn.return_value = '127.0.0.1'
        self.assertEqual('127.0.0.1', resolve('localhost'))

    @mock.patch('socket.gethostbyname')
    def test_host_with_port_resolves_and_keeps_port(self, ghbn):
        ghbn.return_value = '127.0.0.1'
        self.assertEqual('127.0.0.1:8080', resolve('localhost:8080'))

    @mock.patch('socket.gethostbyname',
            side_effect=socket.gaierror('lookup failed'))
    def test_socket_error_shows_hostname(self, ghbn):
        try:
            resolve('localhost')
        except socket.gaierror, e:
            self.assertEquals('lookup failed (localhost)', str(e))


class InputTests(unittest.TestCase):

    @mock.patch('__builtin__.raw_input')
    def test_input(self, raw_input):
        raw_input.return_value = 'asdf'
        out = StringIO()
        self.assertEquals('asdf', input('foo', out))
        self.assertEquals('foo', out.getvalue())


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
            self.assertRaises(Exception, locked2.__enter__)


class NotifyTests(unittest.TestCase):

    @mock.patch('subprocess.check_call')
    def test_notify_calls_notify_send(self, call):
        notify('foo', 'bar')
        call.assert_called_with(['notify-send', 'foo', 'bar'])

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
