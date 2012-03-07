# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

"""batou templating support

Currently we support two templating engines with different formats.

Mako::
    % for server in servers:
    server ${server.name}
    % endfor

Jinja2::
    %% for server in servers
    server {{ server.name }}
    %% endfor
"""

from __future__ import print_function, unicode_literals
import jinja2
import mako.runtime
import mako.template
import StringIO


class TemplateEngine(object):
    """Abstract templating wrapper class.

    Use a subclass that connects to a specific template engine.
    """

    @classmethod
    def get(cls, enginename):
        """Return TemplateEngine instance for `enginename`."""
        if enginename.lower() == 'mako':
            return MakoEngine()
        if enginename.lower() == 'jinja2':
            return Jinja2Engine()
        raise NotImplementedError('template engine not known', enginename)

    def template(self, sourcefile, targetfile, args):
        """Render template from `sourcefile` to `targetfile`.

        Return True if the targetfile has actually been changed.
        """
        interpolated = self._render_template_file(sourcefile, args)
        try:
            with open(targetfile, 'r') as old:
                if old.read() == interpolated.getvalue():
                    return False
        except EnvironmentError:
            pass
        with open(targetfile, 'w') as output:
            output.write(interpolated.getvalue())
        return True

    def _render_template_file(sourcefile, args):
        """Expand template found in `sourcefile` and return it as StringIO."""
        raise NotImplementedError

    def expand(self, templatestr, args):
        """Expand template in `templatestr` and return it as string."""
        raise NotImplementedError


class MakoEngine(TemplateEngine):

    def _render_template_file(self, sourcefile, args):
        args.setdefault('d', '$')
        output = StringIO.StringIO()
        ctx = mako.runtime.Context(output, **args)
        tmpl = mako.template.Template(filename=sourcefile,
                                      strict_undefined=True)
        tmpl.render_context(ctx)
        return output

    def expand(self, templatestr, args):
        args.setdefault('d', '$')
        tmpl = mako.template.Template(templatestr)
        return tmpl.render(**args)


class Jinja2Engine(TemplateEngine):

    def __init__(self, *args, **kwargs):
        super(Jinja2Engine, self).__init__(*args, **kwargs)
        self.env = jinja2.Environment(
            line_statement_prefix='@@',
            undefined=jinja2.StrictUndefined,
            loader=jinja2.FileSystemLoader(['.', '/']))

    def _render_template_file(self, sourcefile, args):
        tmpl = self.env.get_template(sourcefile)
        output = StringIO.StringIO()
        print(tmpl.render(args), file=output)
        return output

    def expand(self, templatestr, args):
        tmpl = self.env.from_string(templatestr)
        return tmpl.render(**args)
