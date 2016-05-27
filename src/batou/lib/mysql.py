from batou import UpdateNeeded
from batou.component import Component
import os
import tempfile


class Command(Component):

    namevar = 'statement'
    admin_password = ''
    admin_user = 'root'
    hostname = None
    port = None

    db = 'mysql'

    # Unless allows you to specify a query that generates output if the
    # target state has been reached already.
    unless = ''

    def configure(self):
        self.statement = self.expand(self.statement)
        self.unless = self.expand(self.unless)

    def _mysql(self, cmd):
        _, self.tmp = tempfile.mkstemp(suffix='sql')
        with open(self.tmp, 'w') as f:
            f.write(cmd+'\n')

        command = [
            'mysql -Bs -u{{component.admin_user}}',
            '-p{{component.admin_password}}']
        if self.hostname:
            command.append('-h {{component.hostname}}')
        if self.port:
            command.append('-P {{component.port}}')
        command.append('{{component.db}} < {{component.tmp}}')

        out, err = self.cmd(self.expand(' '.join(command)))
        os.remove(self.tmp)
        return out, err

    def verify(self):
        if not self.unless:
            raise UpdateNeeded()
        out, err = self._mysql(self.unless)
        if not out.strip():
            raise UpdateNeeded()

    def update(self):
        self._mysql(self.statement)

    @property
    def namevar_for_breadcrumb(self):
        words = self.statement.split()
        if words:
            return ' '.join(words[:2]).upper()
        return '--missing--'


class Database(Component):

    namevar = 'database'
    charset = 'UTF8'
    base_import_file = None
    admin_password = None

    def configure(self):
        create_db = self.expand("""\
CREATE DATABASE IF NOT EXISTS
    {{component.database}}
    DEFAULT CHARACTER SET = '{{component.charset}}';
""")
        self += Command(create_db, admin_password=self.admin_password)

        if self.base_import_file:
            self += Command(
                self.expand('\. {{component.base_import_file}}\n'),
                db=self.database,
                unless=self.expand('show tables'),
                admin_password=self.admin_password)


class User(Component):

    namevar = 'user'
    password = None
    host = 'localhost'
    admin_password = None

    def configure(self):

        create = self.expand("""\
CREATE USER '{{component.user}}'@'{{component.host}}';
""")
        create_unless = self.expand("""\
SELECT *
FROM user
WHERE
    User = '{{component.user}}'
    AND
    Host = '{{component.host}}';
""")
        self += Command(
            create, unless=create_unless, admin_password=self.admin_password)

        set_password = self.expand("""\
SET PASSWORD FOR
    '{{component.user}}'@'{{component.host}}' =
     PASSWORD('{{component.password}}');
""")
        self += Command(set_password, admin_password=self.admin_password)


class Grant(Command):

    namevar = 'grant_db'
    user = ''
    host = 'localhost'
    statement = """\
GRANT ALL
    ON {{component.grant_db}}
    TO '{{component.user}}'@'{{component.host}}';
"""
