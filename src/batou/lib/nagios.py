from batou.component import Component, HookComponent
from batou.lib.file import File
import os.path
import urlparse


class Service(HookComponent):

    namevar = 'description'
    key = 'batou.lib.nagios:Service'

    command = None  # path to executable, if relative then to compdir
    args = ''
    notes_url = ''
    servicegroups = 'direct'

    # dependencies are a list of (host_object, check_description)
    depend_on = ()

    @property
    def check_command(self):
        result = self.command
        if self.args:
            result += '!' + self.args
        return result


class NRPEService(Service):

    name = None
    servicegroups = 'nrpe'

    def configure(self):
        if not self.name:
            self.name = self.description.lower().replace(' ', '_')

    @property
    def check_command(self):
        return 'check_nrpe!%s' % self.name

    @property
    def nrpe_command(self):
        return super(NRPEService, self).check_command


class NagiosServer(Component):
    """Generate a Nagios server config snippet that reflects all active checks.

    The generated config needs to be copied to the Nagios server.

    """

    nagios_cfg = os.path.join(os.path.dirname(__file__),
                             'resources', 'nagios.cfg')

    def configure(self):
        self.services = list(self.require(Service.key))
        self.services.sort(key=lambda x:(x.host.name, x.description))

        self += File(
            self.expand('nagios-server-{{environment.service_user}}.cfg'),
            source=self.nagios_cfg,
            mode=0o644,
            is_template=True)


class NRPEHost(Component):
    """Super-component to create an NRPE server config."""

    # XXX gocept-net specific
    nrpe_cfg = os.path.join(os.path.dirname(__file__),
                            'resources', 'nrpe.cfg')

    def configure(self):
        self.services = [
            service for service in self.require(Service.key, host=self.host)
            if isinstance(service, NRPEService)]

        self += File(self.expand('/etc/nagios/nrpe/local/{{environment.service_user}}.cfg'),
            source=self.nrpe_cfg,
            is_template=True,
            mode=0o644)
