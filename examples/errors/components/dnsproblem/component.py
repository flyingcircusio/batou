from batou.component import Attribute, Component
from batou.utils import Address


class DNSProblem(Component):

    attribute_with_problem = Attribute(Address, 'isnotahostname')

    def configure(self):
        self.require('application')
