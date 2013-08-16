# This code must not cause non-stdlib imports to support self-bootstrapping.


class UpdateNeeded(Exception):
    """A component requires an update."""
    pass


class UnusedResource(Exception):
    """A provided resource was never used."""


class NonConvergingWorkingSet(Exception):
    """A working set did not converge."""
