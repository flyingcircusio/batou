from batou.utils import resolve
import mock
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
