from batou.component import Component


class Program(Component):

    namevar = 'name'

    command = None
    options = {}
    args = ''
    workdir = None  # XXX or default compdir?
    priority = 0

    restart = False  # ... if parent component changed
