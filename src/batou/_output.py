import sys
import traceback


class TerminalBackend(object):

    def __init__(self):
        import py.io
        self._tw = py.io.TerminalWriter(sys.stdout)

    def line(self, message, **format):
        self._tw.line(message, **format)

    def sep(self, sep, title, **format):
        self._tw.sep(sep, title, **format)

    def write(self, content, **format):
        self._tw.write(content, **format)


class ChannelBackend(object):

    def __init__(self):
        self.channel = []

    def line(self, message, **format):
        self.channel.append(('line', (message,), format))

    def sep(self, sep, title, **format):
        self.channel.append(('sep', (sep, title,), format))

    def write(self, content, **format):
        self.channel.append(('write', (content,), format))


class NullBackend(object):

    def __init__(self):
        pass

    def line(self, message, **format):
        pass

    def sep(self, sep, title, **format):
        pass

    def write(self, content, **format):
        pass


class Output(object):
    """Manage the output of various parts of batou to achieve
    consistency wrt to formatting and display.
    """

    enable_debug = False

    def __init__(self, backend):
        self.backend = backend

    def line(self, message, **format):
        self.backend.line(message, **format)

    def annotate(self, message, **format):
        lines = message.split('\n')
        lines = [' ' * 5 + line for line in lines]
        message = '\n'.join(lines)
        self.line(message, **format)

    def tabular(self, key, value, separator=': ', **kw):
        message = key.rjust(10) + separator + value
        self.annotate(message, **kw)

    def section(self, title, **format):
        self.backend.sep("=", title, bold=True, **format)

    def step(self, context, message, **format):
        self.line('{}: {}'.format(context, message),
                  bold=True, **format)

    def debug(self, message, **format):
        if not self.enable_debug:
            return
        self.annotate(message, **format)

    def error(self, message, exc_info=None):
        self.step("ERROR", message, red=True)
        if exc_info:
            tb = traceback.format_exception(*exc_info)
            tb = ''.join(tb)
            tb = '      ' + tb.replace('\n', '\n      ') + '\n'
            self.backend.write(tb, red=True)


output = Output(NullBackend())
