# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.component import Component, Buildout
from batou.tests import TestCase
import mock
import os
import os.path
import shutil
import sysconfig
import tempfile


class ComponentTests(TestCase):

    def setUp(self):
        self.host = mock.Mock()
        self.config = dict()
        self.component = Component('haproxy', self.host, (), self.config)
        self.component.hooks['haproxy'] = mock.Mock()
        self.host.components = [self.component]
        self.component.environment.hosts = dict(host=self.host)
        self.fixture = os.path.dirname(__file__) + '/fixture/component'

    def test_general_attributes_initialized(self):
        self.component.service.base = '<basedir>'
        self.assertEqual('haproxy', self.component.name)
        self.assertIs(self.host, self.component.host)
        self.assertIs(self.host.environment, self.component.environment)
        self.assertIs(self.host.environment.service, self.component.service)
        self.assertTrue('<basedir>/work/haproxy', self.component.compdir)

    # component wire-up

    def test_find_components_only_returns_if_tag_matches_no_host_given(self):
        self.assertRaises(RuntimeError, self.component.find_hooks, 'asdf')
        self.assertEqual(
            [self.component.hooks['haproxy']],
            list(self.component.find_hooks('haproxy')))

    def test_find_components_only_returns_if_tag_and_host_matches(self):
        self.assertRaises(RuntimeError,
                          self.component.find_hooks, 'haproxy', mock.Mock())
        self.assertEqual(
            [self.component.hooks['haproxy']],
            list(self.component.find_hooks('haproxy', self.host)))

    # convenience api

    def test_install_should_create_leading_dirs(self):
        with open('myfile', 'w') as f:
            print('hello world', file=f)
        self.component.install('myfile', 'tmp-a/b/c/d/myfile')
        self.assertFileExists('tmp-a/b/c/d/myfile')
        os.unlink('myfile')
        shutil.rmtree('tmp-a')

    def test_install_should_set_mode(self):
        with open('myfile1', 'w') as f:
            print('hello world', file=f)
        self.component.install('myfile1', 'myfile2', mode=0o654)
        self.assertEqual(os.stat('myfile2').st_mode & 0o7777, 0o654)
        os.unlink('myfile1')
        os.unlink('myfile2')

    def test_install_should_do_nothing_if_identical(self):
        with tempfile.NamedTemporaryFile(prefix='install') as tf:
            shutil.copyfile('%s/haproxy.cfg' % self.fixture, tf.name)
            os.utime(tf.name, (1, 1))
            self.component.install('%s/haproxy.cfg' % self.fixture, tf.name)
            self.assertEqual(1, os.stat(tf.name).st_mtime)
            self.assertEqual(set(), self.component.changed_files)

    def test_install_should_record_changed_file(self):
        with tempfile.NamedTemporaryFile(prefix='install') as tf:
            self.component.install('%s/haproxy.cfg' % self.fixture, tf.name)
            self.assertEqual(set([tf.name]), self.component.changed_files)

    def test_chdir(self):
        olddir = os.getcwd()
        with self.component.chdir('/tmp'):
            self.assertEqual('/tmp', os.getcwd())
        self.assertEqual(olddir, os.getcwd())

    # template api

    def test_expand(self):
        self.assertEqual('hello haproxy',
                         self.component.expand('hello ${component.name}'))

    def test_template_should_do_nothing_if_identical(self):
        with tempfile.NamedTemporaryFile(prefix='install') as tf:
            with open(tf.name, 'w') as interpolated:
                interpolated.write("""\
frontend
        name haproxy
""")
            os.utime(tf.name, (1, 1))
            self.component.template('%s/haproxy.cfg' % self.fixture, tf.name)
            self.assertEqual(1, os.stat(tf.name).st_mtime,
                             'file has been touched')
            self.assertEqual(set(), self.component.changed_files)

    def test_template_should_record_changed_file(self):
        with tempfile.NamedTemporaryFile(prefix='install') as tf:
            self.component.template('%s/haproxy.cfg' % self.fixture, tf.name)
            self.assertEqual(set([tf.name]), self.component.changed_files)


class BuildoutTests(TestCase):

    @mock.patch('os.symlink')
    def test_determine_python_config(self, symlink):
        c = Buildout(mock.Mock(), mock.Mock(), mock.Mock(), mock.Mock())
        c.python = 'python%s' % sysconfig.get_python_version()
        c._install_python_config()
        self.assertTrue(symlink.called)
