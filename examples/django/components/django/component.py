from batou.component import Component
from batou.lib.python import AppEnv
from batou.lib.file import SyncDirectory
from batou.lib.supervisor import Program
from batou.utils import Address


class Django(Component):

    def configure(self):
        self.address = Address(self.host.fqdn, '8081')
        self += AppEnv('3.6')

        self += SyncDirectory('mysite', source='mysite')

        self += Program(
            'django',
            command='bin/python',
            deployment='cold',
            options={'stopasgroup': 'true'},
            args=self.expand('mysite/manage.py runserver '
                             ' {{component.address.listen}}'))
