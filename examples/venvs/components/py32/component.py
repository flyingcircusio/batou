from batou.component import Component
from batou.lib.buildout import Buildout


class Py32(Component):

    def configure(self):
        buildout = Buildout(
            python='3.2',
            setuptools='1.4.1',
            version='2.2.1')
        self += buildout
