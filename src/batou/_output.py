import sys
from batou.remote_core import Output


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


class NullBackend(object):

    def line(self, message, **format):
        pass

    def sep(self, sep, title, **format):
        pass

    def write(self, content, **format):
        pass


output = Output(NullBackend())
