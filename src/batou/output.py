import py.io
import sys
import traceback


class Output(object):
    """Manage the output of various parts of batou to achieve
    consistency wrt to formatting and display.
    """

    def __init__(self):
        self._tw = py.io.TerminalWriter(sys.stdout)

    def annotate(self, message, **format):
        lines = message.split('\n')
        lines = [' ' * 5 + line for line in lines]
        message = '\n'.join(lines)
        self._tw.line(message, **format)

    def tabular(self, key, value, separator=': ', **kw):
        message = key.rjust(10) + separator + value
        self.annotate(message, **kw)

    def section(self, title, **format):
        self._tw.sep("=", title, bold=True, **format)

    def step(self, context, message, **format):
        self._tw.line('{}: {}'.format(context, message),
                      bold=True, **format)

    def error(self, message, exc_info=None):
        self.step("ERROR", message, red=True)
        if exc_info:
            tb = traceback.format_exception(*exc_info)
            tb = ''.join(tb)
            tb = '      ' + tb.replace('\n', '\n      ') + '\n'
            self._tw.write(tb, red=True)


output = Output()
