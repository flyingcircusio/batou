"""batou templating support

Currently we support one templating engine:

Jinja2::
    {% for server in servers %}
    server {{ server.name }}
    {% endfor %}

"""

from __future__ import print_function, unicode_literals
import jinja2
import StringIO


class TemplateEngine(object):
    """Abstract templating wrapper class.

    Use a subclass that connects to a specific template engine.
    """

    @classmethod
    def get(cls, enginename):
        """Return TemplateEngine instance for `enginename`."""
        if enginename.lower() == 'jinja2':
            return Jinja2Engine()
        raise NotImplementedError('template engine not known', enginename)

    def template(self, sourcefile, args):
        """Render template from `sourcefile` and return the value.
        """
        return self._render_template_file(sourcefile, args).getvalue()

    def _render_template_file(self, sourcefile, args):
        """Expand template found in `sourcefile` and return it as StringIO."""
        raise NotImplementedError

    def expand(self, templatestr, args):
        """Expand template in `templatestr` and return it as string."""
        raise NotImplementedError


class Jinja2Engine(TemplateEngine):

    def __init__(self, *args, **kwargs):
        super(Jinja2Engine, self).__init__(*args, **kwargs)
        self.env = jinja2.Environment(
            line_statement_prefix='@@',
            keep_trailing_newline=True,
            undefined=jinja2.StrictUndefined)

    def _render_template_file(self, sourcefile, args):
        tmpl = open(sourcefile).read()
        tmpl = self.env.from_string(tmpl)
        output = StringIO.StringIO()
        print(tmpl.render(args), file=output)
        return output

    def expand(self, templatestr, args, identifier='<template>'):
        tmpl = self.env.from_string(templatestr)
        tmpl.filename = identifier
        return tmpl.render(**args)
