# This code must not cause non-stdlib imports to support self-bootstrapping.


class ExplainableException(Exception):
    """This exception provides an API that allows batou to display
    a reasonable error message without having to show tracebacks.
    """

    def explain(self):
        """Explain yourself. :)

        Return a unicode string.

        """
        raise NotImplementedError


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
