# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.utils import host_from_uri, resolve
import mock
import unittest


class HostFromUriTests(unittest.TestCase):

    def test_source_host_from_simple_url(self):
        self.assertEqual(
            'example.com', host_from_uri('http://example.com'))

    def test_source_host_ignores_port(self):
        self.assertEqual(
            'example.com', host_from_uri('http://example.com:80'))

    def test_source_host_ignores_user(self):
        self.assertEqual(
            'example.com', host_from_uri('http://user@example.com'))

    def test_source_host_ignores_user_and_port(self):
        self.assertEqual(
            'example.com', host_from_uri('http://user@example.com:80'))


class ResolveTests(unittest.TestCase):

    @mock.patch('socket.gethostbyname')
    def test_host_without_port_resolves(self, ghbn):
        ghbn.return_value = '127.0.0.1'
        self.assertEqual('127.0.0.1', resolve('localhost'))

    @mock.patch('socket.gethostbyname')
    def test_host_with_port_resolves_and_keeps_port(self, ghbn):
        ghbn.return_value = '127.0.0.1'
        self.assertEqual('127.0.0.1:8080', resolve('localhost:8080'))
