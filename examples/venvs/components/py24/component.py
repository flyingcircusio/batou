from batou.component import Component
from batou.lib.buildout import Buildout


class Py24(Component):

    def configure(self):
        buildout = Buildout(
            python='2.4',
            setuptools='1.3.2',
            version='1.7.0')
        self += buildout
