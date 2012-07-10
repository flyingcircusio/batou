"""Manage service components for individual hosts."""


class Host(object):
    """Description of service components for a host."""

    def __init__(self, fqdn, environment):
        self.environment = environment
        self.fqdn = fqdn
        self.name = self.fqdn.split('.')[0]
        self.components = []

    # XXX this method is a smell for refactoring
    def add_component(self, name, features=None):
        """Register a top-level component as defined in the service
        for this host.
        """
        root_factory = self.environment.service.components[name]
        root = root_factory(self.environment.service, self.environment,
                            self, features, {})
        self.components.append(root)
        return root

    def __getitem__(self, name):
        """Return a top-level component by name."""
        for component in self.components:
            if component.name == name:
                return component
