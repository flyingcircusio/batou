from batou.component import Component
from batou.lib.buildout import Buildout


class Py25(Component):

    def configure(self):
        buildout = Buildout(
            python='2.5',
            setuptools='1.3.2',
            version='1.7.1')
        self += buildout
