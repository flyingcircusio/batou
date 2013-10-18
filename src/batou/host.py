"""Manage service components for individual hosts."""


class Host(object):
    """Description of service components for a host."""

    def __init__(self, fqdn):
        self.fqdn = fqdn
        self.name = self.fqdn.split('.')[0]
