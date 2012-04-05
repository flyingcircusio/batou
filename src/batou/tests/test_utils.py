# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.utils import host_from_uri, resolve, string_list, convert_type
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


class StringList(unittest.TestCase):

    def test_empty_string_returns_empty_list(self):
        self.assertEquals([], string_list(''))
        self.assertEquals([], string_list('  '))

    def test_comma_separates_items(self):
        self.assertEquals(['a', 'b', 'c'], string_list('a,b,c'))

    def test_whitespace_is_stripped(self):
        self.assertEquals(['a', 'b', 'c'], string_list(' a , b , c '))

    def test_single_item_returns_list_with_single_item(self):
        self.assertEquals(['a'], string_list('a'))

    def test_single_item_is_stripped(self):
        self.assertEquals(['a'], string_list('a '))


class ConvertTypeTest(unittest.TestCase):

    def test_str(self):
        self.assertEqual('1', convert_type(1, 'str'))

    def test_int(self):
        self.assertEqual(2, convert_type('2', 'int'))

    def test_float(self):
        self.assertEqual(3.6, convert_type('3.6', 'float'))

    def test_bool(self):
        self.assertEqual(True, convert_type('yes', 'bool'))
        self.assertEqual(True, convert_type('on', 'bool'))
        self.assertEqual(False, convert_type('n', 'bool'))
        self.assertEqual(False, convert_type('no', 'bool'))
        self.assertEqual(False, convert_type('false', 'bool'))
        self.assertEqual(False, convert_type('off', 'bool'))

    def test_list(self):
        self.assertEqual(['one', 'two'], convert_type('one, two', 'list'))
