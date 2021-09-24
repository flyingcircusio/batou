from batou.component import Component
from batou.utils import Address


class DNSProblem2(Component):

    attribute_without_v6 = Address("localhost:22", require_v6=False)

    def configure(self):
        # Accessing `listen_v6` causes an error:
        self.attribute_without_v6.listen_v6
