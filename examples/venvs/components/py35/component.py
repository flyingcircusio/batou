from batou.component import Component
from batou.lib.buildout import Buildout


class Py35(Component):
    def configure(self):
        buildout = Buildout(python="3.5", setuptools="18.3.1", version="2.4.3")
        self += buildout
