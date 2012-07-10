# Ensure platform components have a chance to register.

# XXX make more flexible. E.g. by using entry points.
import batou.lib.goceptnet  # noqa

# API re-exports
from .component import Component  # noqa


class UpdateNeeded(Exception):
    """A component requires an update."""
    pass


class UnusedResource(Exception):
    """A provided resource was never used."""


class NonConvergingWorkingSet(Exception):
    """A working set did not converge."""
