from batou.component import Component


class Check(Component):

    namevar = 'description'

    type = 'nrpe'
    host = None
    command = None  # path to executable, if relative then to compdir
    args = None
    name = None  # by default derived automatically from description


class Nagios(Component):

    def configure(self):
        pass
