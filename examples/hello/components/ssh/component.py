from batou.component import Component


def prepare_key(key):
    return key.strip()+'\n'


class SSHDir(Component):
    """A collector component that expects a platform to insert the specific
    SSH directory to be stored in 'sshdir'.
    """

    path = ''


class KnownHosts(Component):
    """Install SSH host keys into `known_hosts` in the working directory.

    Scans for hosts that are missing from the file. Leaves additional hosts
    alone.
    """

    hosts = []

    def configure(self):
        self += SSHDir()
        self += file.Presence('known_hosts')

    def verify(self):
        for line in open('known_hosts', 'r'):
            if not ' ' in line:
                continue
            host, _ = line.split(' ', 1)
            if host in hosts:
                hosts.remove(host)
        if hosts:
            raise UpdateNeeded()

    def update(self):
        # Disable ssh agent. (XXX Why? I'm guessing this is related to the
        # key scan.)
        try:
            del os.environ['SSH_AUTH_SOCK']
        except KeyError:
            pass
        with open('known_hosts', 'wa') as known_hosts:
            for host in self.hosts:
                known_hosts.write(self.cmd('ssh-keyscan {}'))


class SSHKeyPair(Component):
    """Install SSH key pair.

    User keys are read from the secrets file and written to
    ~/.ssh/id_dsa{,.pub}.

    This component installs all needed files to its work directory and
    requires a platform to copy/symlink them to the right place eventually.
    """

    def configure(self):
        sshdir = SSHDir()
        self += sshdir
        id_dsa = self.secrets.get('ssh', 'id_dsa')
        if id_dsa:
            id_dsa = prepare_key(id_dsa)
            id_dsa_path = os.path.join(sshdir.path, 'id_dsa')
            self += file.Content(id_dsa_path, content=id_dsa)
            self += file.Mode(id_dsa_path, 0o600)

        id_dsa_pub = secrets.get('ssh', 'id_dsa.pub')
        if id_dsa_pub:
            id_dsa_pub = prepare_key(id_dsa_pub)
            id_dsa_pub_path = os.path.join(sshdir.path, 'id_dsa.pub')
            self += file.Content(id_dsa_pub_path, content=id_dsa_pub)
