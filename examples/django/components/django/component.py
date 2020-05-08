from batou.component import Component
from batou.lib.python import AppEnv
from batou.lib.file import SyncDirectory, File
from batou.lib.supervisor import Program
from batou.utils import Address


class Django(Component):

    def configure(self):
        self.address = Address(self.host.fqdn, '8081')
        self += AppEnv('3.7')

        self += SyncDirectory('mysite', source='mysite')

        self += File('foo', content='asdf\nbsdf\ncsdf')

        self += Program(
            'django',
            command='bin/python',
            deployment='cold',
            options={'stopasgroup': 'true'},
            args=self.expand('mysite/manage.py runserver '
                             ' {{component.address.listen}}'))
