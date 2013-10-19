from batou.component import Component
from batou.lib.python import VirtualEnv, Package
from batou.lib.file import SyncDirectory
from batou.lib.supervisor import Program
from batou.utils import Address


class Django(Component):

    def configure(self):
        self.address = Address(self.host.fqdn, '8080')
        self += VirtualEnv('2.7')
        self += Package('Django',
                        version='1.5.4')
        self += SyncDirectory('mysite', source='mysite')
        self += Program(
            'django',
            command='bin/python',
            args=self.expand('mysite/manage.py runserver '
                             ' {{component.address.listen}}'))
