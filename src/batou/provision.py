import os
import os.path
import tempfile
import uuid

from batou.utils import cmd


class Provisioner(object):

    rebuild = False

    def __init__(self, name):
        self.name = name

    @classmethod
    def from_config_section(cls, section):
        return NotImplemented

    def provision(self, host):
        pass

    def suggest_name(self, name):
        return name


class FCDevContainer(Provisioner):

    target_host = None
    aliases = ()
    nix_config = None  # Filename

    @classmethod
    def from_config_section(cls, name, section):
        instance = FCDevContainer(name)
        instance.target_host = section['host']
        instance.aliases = section.get('aliases', [])
        return instance

    def suggest_name(self, name):
        config = "-F ssh_config" if os.path.exists('ssh_config') else ''
        out, _ = cmd(
            "ssh {config} {target_host} 'sudo nixos-container list'".format(
                config=config, target_host=self.target_host))
        names = filter(None, [x.strip() for x in out.splitlines()])
        while True:
            name = uuid.uuid4().hex[:11]
            if name not in names:
                return name

    def _prepare_ssh(self, host):
        container = host.name

        # XXX application / user-specific files
        # https://unix.stackexchange.com/questions/312988/understanding-home-configuration-file-locations-config-and-local-sha
        KNOWN_HOSTS_FILE = os.path.expanduser('~/.batou/known_hosts')

        if not os.path.exists(KNOWN_HOSTS_FILE):
            os.makedirs(os.path.dirname(KNOWN_HOSTS_FILE))
            with open(KNOWN_HOSTS_FILE, 'w'):
                pass

        if self.rebuild:
            cmd(['ssh-keygen', '-R', container, '-f', KNOWN_HOSTS_FILE])

        ssh_config = []
        if os.path.exists(os.path.expanduser('~/.ssh/config')):
            ssh_config.append('Include ~/.ssh/config')
        if os.path.exists('ssh_config'):
            ssh_config.append('Include {}'.format(
                os.path.abspath('ssh_config')))

        # We need to provide a version of the key that doesn't trigger
        # OpenSSHs "wrong permission" check.
        packaged_insecure_key = os.path.join(
            os.path.dirname(__file__), 'insecure-private.key')
        local_insecure_key = os.path.abspath('insecure-private.key')
        with open(local_insecure_key, 'w') as f_target:
            with open(packaged_insecure_key) as f_packaged:
                f_target.write(f_packaged.read())
        os.chmod(local_insecure_key, 0o600)

        ssh_config.append("""
Host {container} {aliases}
    HostName {container}
    ProxyJump {target_host}
    User developer
    IdentityFile {insecure_private_key}
    StrictHostKeyChecking no
    UserKnownHostsFile {known_hosts}
""".format(container=container,
           aliases=' '.join(host.aliases),
           target_host=self.target_host,
           known_hosts=KNOWN_HOSTS_FILE,
           insecure_private_key=local_insecure_key))

        # Place this in the deployment base directory persistently and
        # keep updating it. This helps users to also interact with containers
        # by running `ssh -F ssh_config_dev mycontainer`
        self.ssh_config_file = os.path.abspath('ssh_config_{}'.format(
            host.environment.name))
        with open(self.ssh_config_file, 'w') as f:
            f.write('\n'.join(ssh_config))

    def provision(self, host):
        container = host.name
        self._prepare_ssh(host)

        env = {
            'PROVISION_CONTAINER': container,
            'PROVISION_HOST': self.target_host,
            'SSH_CONFIG': self.ssh_config_file,
            'RSYNC_RSH': 'ssh -F {}'.format(self.ssh_config_file)}
        if self.rebuild:
            env['PROVISION_REBUILD'] = '1'
        # Add all component variables (uppercased) to the environment
        # $COMPONENT_<component>_<variable>
        # this includes environment overrides and secrets.
        for root_name, root in host.components.items():
            root = root.factory
            for name in dir(root):
                if name.startswith('_'):
                    continue
                if name in ['changed', 'workdir', 'namevar']:
                    continue
                value = getattr(root, name)
                if callable(value):
                    continue
                if isinstance(value, property):
                    continue
                key = 'COMPONENT_{}_{}'.format(root_name, name)
                key = key.upper()
                env[key] = str(value)
            for name, value in host.environment.overrides.get(root_name,
                                                              {}).items():
                key = 'COMPONENT_{}_{}'.format(root_name, name)
                key = key.upper()
                env[key] = str(value)

        seed_script_file = 'environments/{}/provision.sh'.format(
            host.environment.name)
        if os.path.exists(seed_script_file):
            seed_script = """\
# BEGIN CUSTOM SEED SCRIPT
cd {basedir}
{script}
# END CUSTOM SEED SCRIPT
""".format(basedir=os.path.dirname(seed_script_file),
            script=open(seed_script_file).read())
        else:
            seed_script = ''

        _, provision_script = tempfile.mkstemp()
        try:
            os.chmod(provision_script, 0o700)
            with open(provision_script, 'w') as f:
                # We're placing the ENV vars directly in the script because
                # that helps debugging a lot. We need to be careful to
                # deleted it later, though, because it might contain secrets.
                f.write("""\
#/bin/sh
set -ex

{ENV}

ECHO() {{
    what=${{1?what to echo}}
    where=${{2?where to echo}}
    RUN "echo $what > $where"
}}

RUN() {{
    cmd=$@
    ssh -F $SSH_CONFIG $PROVISION_CONTAINER "$cmd"
}}

COPY() {{
    what=${{1?what to copy}}
    where=${{2?where to copy}}
    rsync $what $PROVISION_CONTAINER:$where
}}

if [ ${{PROVISION_REBUILD+x}} ]; then
    ssh $PROVISION_HOST fc-build-dev-container destroy $PROVISION_CONTAINER
fi

ssh $PROVISION_HOST fc-build-dev-container ensure $PROVISION_CONTAINER

{seed_script}

RUN sudo -i fc-manage -b

""".format(seed_script=seed_script,
                ENV='\n'.join(
                sorted('export {}="{}"'.format(k, v) for k, v in env.items()))))
            cmd(provision_script)
        finally:
            # The script includes secrets so we must be sure that we delete
            # it.
            os.unlink(provision_script)
