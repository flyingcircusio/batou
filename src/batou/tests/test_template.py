# -*- coding: utf-8 -*-
from batou.template import TemplateEngine
import collections
import jinja2
import mock
import os.path
import pytest


Server = collections.namedtuple('Server', ['name', 'address'])


sample_dict = dict(
    host=mock.Mock(),
    config=dict(),
    servers=[Server('s1', '1.2.3.4'), Server('s2', '2.3.4.5')],
    hello='world',
    hello2=u'wörld')

fixture = '%s/fixture/template' % os.path.dirname(__file__)


def test_unknown_template_engine():
    with pytest.raises(NotImplementedError):
        TemplateEngine.get('foo')


def test_abstract_engine():
    engine = TemplateEngine()
    with pytest.raises(NotImplementedError):
        engine._render_template_file("asdf", {})
    with pytest.raises(NotImplementedError):
        engine.expand("asdf", {})


def test_jinja2_template_str():
    tmpl = TemplateEngine.get('jinja2')
    assert 'hello world' == tmpl.expand('hello {{hello}}', sample_dict)


def test_jinja2_template_file():
    tmpl = TemplateEngine.get('jinja2')
    filename = '{}/haproxy.cfg'.format(fixture)
    result = tmpl.template(filename + '.jinja2', sample_dict)
    with open(filename) as ref:
        assert ref.read() == result


def test_jinja2_unknown_variable_should_fail():
    tmpl = TemplateEngine.get('jinja2')
    with pytest.raises(jinja2.UndefinedError):
        tmpl.expand('unknown variable {{foo}}', {})


def test_jinja2_umlaut_variables():
    tmpl = TemplateEngine.get('jinja2')
    assert u'hello wörld' == tmpl.expand('hello {{hello2}}', sample_dict)
