# Ensure platform components have a chance to register.

# XXX make more flexible. E.g. by using entry points.
import batou.lib.goceptnet  # noqa
batou  # Make pyflakes happy
# API re-exports
from .component import Component  # noqa
Component  # Make pyflakes happy


class UpdateNeeded(Exception):
    """A component requires an update."""
    pass


class UnusedResource(Exception):
    """A provided resource was never used."""


class NonConvergingWorkingSet(Exception):
    """A working set did not converge."""
