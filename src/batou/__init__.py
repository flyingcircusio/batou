# This code must not cause non-stdlib imports to support self-bootstrapping.


class UpdateNeeded(Exception):
    """A component requires an update."""
    pass


class UnusedResource(Exception):
    """A provided resource was never used."""


class NonConvergingWorkingSet(Exception):
    """A working set did not converge."""

    def __str__(self):
        message = []
        for component in self.args[0]:
            message.append('    '+component.name)
        message.sort()
        return '\n'+'\n'.join(message)
