from batou.component import Component


class Service(Component):
    """A generic component to provide a system service.

    Platform-specific components need to perform the work necessary
    to ensure startup and shutdown of the executable correctly.
    """

    namevar = 'executable'

    pidfile = None  # The pidfile as written by the services' executable.
