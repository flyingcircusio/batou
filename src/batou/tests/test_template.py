from __future__ import print_function, unicode_literals
from batou.template import TemplateEngine
from batou.tests import TestCase
import collections
import jinja2
import mock
import os.path


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

    def test_abstract_engine(self):
        engine = TemplateEngine()
        with self.assertRaises(NotImplementedError):
            engine._render_template_file("asdf", {})
        with self.assertRaises(NotImplementedError):
            engine.expand("asdf", {})

    def test_jinja2_template_str(self):
        tmpl = TemplateEngine.get('jinja2')
        self.assertEqual('hello world',
                         tmpl.expand('hello {{hello}}', self.__dict__))

    def _template_runner(self, template_format, source):
        tmpl = TemplateEngine.get(template_format)
        result = tmpl.template(source, self.__dict__)
        with open('%s/haproxy.cfg' % self.fixture) as ref:
            self.assertMultiLineEqual(ref.read(), result)

    def test_jinja2_template_file(self):
        self._template_runner('jinja2', '%s/haproxy.cfg.jinja2' % self.fixture)

    def test_jinja2_unknown_variable_should_fail(self):
        tmpl = TemplateEngine.get('jinja2')
        with self.assertRaises(jinja2.UndefinedError):
            tmpl.expand('unknown variable {{foo}}', {})
