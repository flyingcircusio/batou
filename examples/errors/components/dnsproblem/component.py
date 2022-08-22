from batou.component import Attribute, Component, ConfigString
from batou.utils import Address


class DNSProblem(Component):

    attribute_with_problem = Attribute(
        Address, default=ConfigString("isnotahostname")
    )

    def configure(self):
        self.require("application")
