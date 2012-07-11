from StringIO import StringIO
from batou.utils import resolve, input
import mock
import sys
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


class InputTests(unittest.TestCase):

    @mock.patch('__builtin__.raw_input')
    def test_input(self, raw_input):
        raw_input.return_value = 'asdf'
        out = StringIO()
        self.assertEquals('asdf', input('foo', out))
        self.assertEquals('foo', out.getvalue())
