from batou.component import Component
from batou.lib.package import DPKG


class CouchDB(Component):

    def configure(self):
        self += DPKG("couchdb")
