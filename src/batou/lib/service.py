from batou.component import Component


class Service(Component):
    """A generic component to provide a system service.

    Platform-specific components need to perform the work necessary
    to ensure startup and shutdown of the executable correctly.
    """

    namevar = 'executable'

    pidfile = None  # The pidfile as written by the services' executable.

    def start(self):
        """Start service.

        The actual work *should* be done by platform-specific components. If
        there is no platform-specific component handling the start, the
        executable is executed for reasons of backward compatibility.

        """
        if self._platform_component is not None:
            assert self._platform_component._prepared
            start = getattr(self._platform_component, 'start', None)
            if callable(start):
                start()
                return
        self.cmd(self.executable)
