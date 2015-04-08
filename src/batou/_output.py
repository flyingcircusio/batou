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

    def __init__(self, channel):
        self.channel = channel

    def _send(self, output_cmd, *args, **kw):
        self.channel.send(('batou-output', output_cmd, args, kw))

    def line(self, message, **format):
        self._send('line', message, **format)

    def sep(self, sep, title, **format):
        self._send('sep', sep, title, **format)

    def write(self, content, **format):
        self._send('write', content, **format)


class NullBackend(object):

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

    def line(self, message, debug=False, **format):
        if debug and not self.enable_debug:
            return
        self.backend.line(message, **format)

    def annotate(self, message, debug=False, **format):
        if debug and not self.enable_debug:
            return
        lines = message.split('\n')
        lines = [' ' * 5 + line for line in lines]
        message = '\n'.join(lines)
        self.line(message, **format)

    def tabular(self, key, value, separator=': ', debug=False, **kw):
        if debug and not self.enable_debug:
            return
        message = key.rjust(10) + separator + value
        self.annotate(message, **kw)

    def section(self, title, debug=False, **format):
        if debug and not self.enable_debug:
            return
        self.backend.sep("=", title, bold=True, **format)

    def step(self, context, message, debug=False, **format):
        if debug and not self.enable_debug:
            return
        self.line('{}: {}'.format(context, message),
                  bold=True, **format)

    def error(self, message, exc_info=None, debug=False):
        if debug and not self.enable_debug:
            return
        self.step("ERROR", message, red=True)
        if exc_info:
            tb = traceback.format_exception(*exc_info)
            tb = ''.join(tb)
            tb = '      ' + tb.replace('\n', '\n      ') + '\n'
            self.backend.write(tb, red=True)


output = Output(NullBackend())
