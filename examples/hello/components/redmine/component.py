from batou.component import Component

# download mirroring und secrets sind ein orthogonales feature
# der download-komponente!

# E.g. mirror: <urlteil> -> neuer urlteil + secrets

# download. target ist by default: letzter dateiname + 'download' im workdir

# komponenten ohne sub- und mit leeren (notimplemented oder so) verify/update 
# sollten einen fehler oder eine warnung ausspucken


class Redmine(Component):

    release = '1.4.1'
    hostname = 'localhost'
    port = 8087

    def configure(self):
        self += Download('http://download.redmine.org/redmine-%s.tar.gz')
        self += ExtractedArchive()
        self += RubyBundlerApp()

        self += File({
            'redmine/config/database.yml': dict(
                template='database.yml.in'),
            'redmine/config/initializers/session_store.rb': dict(
                template='session_store.rb.in'),
            'redmine/public/dispatch.fcgi': dict(
                template='dispatch.cfg.in',
                mode=0o755),
            'spawn.sh': dict(
                template='spawn.sh.in',
                mode=0o755)})

        self += RailsDBMigrate()
        self += DBConfiguration()
        self += RailsFCGIServer('redmine',
                uri='/redmine',
                basedir='{}/redmine/public'.format(self.workdir))

        self += MailAlias

        self += SupervisorService()

        self += MySQLDB()
