from batou.component import Attribute, Component
from batou.utils import Address


class DNSProblem(Component):

    attribute_with_problem = Attribute(
        Address, default_conf_string="isnotahostname"
    )

    def configure(self):
        self.require("application")
