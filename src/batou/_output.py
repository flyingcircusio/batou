import os
import sys

from batou.remote_core import Output


class TerminalBackend(object):
    def __init__(self):
        import py.io

        self._tw = py.io.TerminalWriter(sys.stdout)

        if os.environ.get("IN_TOX_TEST") == "1":
            self._tw.fullwidth = 80

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


class TestBackend(object):
    def __init__(self):
        self.output = ""

    def line(self, message, **format):
        self.output += message + "\n"

    def sep(self, sep, title, **format):
        self.output += " {} {} {} ".format(sep * 3, title, sep * 3)

    def write(self, content, **format):
        self.output += content + "\n"


output = Output(NullBackend())
