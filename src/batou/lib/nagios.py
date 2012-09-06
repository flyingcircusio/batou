from batou.component import Component
from batou.lib.file import File
import urlparse


class Check(Component):

    namevar = 'description'
    key = 'batou.lib.nagios:Check'

    args = ''
    command = None  # path to executable, if relative then to compdir
    host = None
    name = None  # by default derived automatically from description
    notes_url = ''
    type = 'nrpe'

    # dependencies are a list of (host_object, check_description)
    depend_on = ()


class HTTPCheck(Check):

    namevar = 'url'

    warning = 4
    critical = 8
    timeout = 30

    def configure(self):
        if not self.description:
            self.description = self.url

        url = urlparse.urlparse(self.url)
        self.ssl = dict(
            http='',
            https='-S')[url.scheme]
        self.httphost = url.netloc
        self.urlpath = url.path


class NagiosServer(Component):
    """Generate a Nagios server config snippet that reflects all active checks.

    The generated config needs to be copied to the Nagios server.

    """

    def configure(self):
        self.checks = self.require(Check.key)
        self += File('nagios.cfg',
                     source='nagios.cfg',
                     mode=0o644,
                     is_template=True)
