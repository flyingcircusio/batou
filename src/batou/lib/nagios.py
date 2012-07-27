from batou.component import Component


class Check(Component):

    namevar = 'description'

    type = 'nrpe'
    host = None
    command = None # path to executable, if relative then to compdir
    args = None
    name = None # by default derived automatically from description



class Nagios(Component):

    timeout = 3
    extends = ()    # Extends need to be aspects that have a path
    config = None

    def configure(self):
        if self.config is None:
            self.config = File('buildout.cfg',
                               source='buildout.cfg',
                               template_context=self.parent,
                               is_template=True)
        if isinstance(self.config, Component):
            self.config = [self.config]
        for component in self.config:
            self += component
        venv = VirtualEnv(self.python)
        self += venv
        self += Bootstrap(python=venv.python)

    def verify(self):
        config_paths = [x.path for x in self.config]
        self.assert_file_is_current(
            '.installed.cfg', ['bin/buildout'] + config_paths)
        self.assert_file_is_current(
            '.batou.buildout.success', ['.installed.cfg'])

    def update(self):
        self.cmd('bin/buildout -t {}'.format(self.timeout))
        self.touch('.batou.buildout.success')
