from batou.component import Component
from batou.lib.buildout import Buildout


class Py34(Component):

    def configure(self):
        buildout = Buildout(
            python='3.4',
            setuptools='18.3.1',
            version='2.4.3')
        self += buildout
