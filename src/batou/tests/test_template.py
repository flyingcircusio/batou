# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.template import TemplateEngine
from batou.tests import TestCase
import collections
import jinja2
import mock
import os
import os.path
import shutil
import tempfile


Server = collections.namedtuple('Server', ['name', 'address'])


class ComponentTemplateTests(TestCase):

    def setUp(self):
        self.host = mock.Mock()
        self.config = dict()
        self.servers = [Server('s1', '1.2.3.4'), Server('s2', '2.3.4.5')]
        self.hello = 'world'
        self.fixture = '%s/fixture/template' % os.path.dirname(__file__)

    def test_unknown_template_engine(self):
        with self.assertRaises(NotImplementedError):
            TemplateEngine.get('foo')

    def test_mako_template_str(self):
        tmpl = TemplateEngine.get('mako')
        self.assertEqual('hello world',
                         tmpl.expand('hello ${hello}', self.__dict__))

    def test_jinja2_template_str(self):
        tmpl = TemplateEngine.get('jinja2')
        self.assertEqual('hello world',
                         tmpl.expand('hello {{hello}}', self.__dict__))

    def test_mako_dollar_pseudoescape(self):
        tmpl = TemplateEngine.get('mako')
        self.assertEqual('${PATH}', tmpl.expand('${d}{PATH}', {}))

    def _template_runner(self, template_format, source):
        tmpl = TemplateEngine.get(template_format)
        with tempfile.NamedTemporaryFile(prefix='out') as target:
            changed = tmpl.template(source, target.name, self.__dict__)
            self.assertTrue(changed)
            with open('%s/haproxy.cfg' % self.fixture) as ref:
                with open(target.name) as tf:
                    self.assertMultiLineEqual(ref.read(), tf.read())

    def test_mako_template_file(self):
        self._template_runner('mako', '%s/haproxy.cfg.mako' % self.fixture)

    def test_jinja2_template_file(self):
        self._template_runner('jinja2', '%s/haproxy.cfg.jinja2' % self.fixture)

    def test_expand_should_return_false_if_unchanged(self):
        tmpl = TemplateEngine.get('jinja2')
        source = '%s/haproxy.cfg' % self.fixture
        with tempfile.NamedTemporaryFile(prefix='out') as target:
            shutil.copyfile(source, target.name)
            #import pdb; pdb.set_trace()
            changed = tmpl.template(source, target.name, self.__dict__)
            self.assertFalse(changed)


    def test_jinja2_unknown_variable_should_fail(self):
        tmpl = TemplateEngine.get('jinja2')
        with self.assertRaises(jinja2.UndefinedError):
            tmpl.expand('unknown variable {{foo}}', {})
