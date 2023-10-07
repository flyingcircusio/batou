import os
import os.path
import shlex
import socket
import tempfile
import textwrap
import uuid

import batou.utils
from batou import output
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


class FCDevProvisioner(Provisioner):
    target_host = None
    aliases = ()

    def _prepare_ssh(self, host):
        # XXX application / user-specific files
        # https://unix.stackexchange.com/questions/312988/understanding-home-configuration-file-locations-config-and-local-sha
        KNOWN_HOSTS_FILE = os.path.expanduser("~/.batou/known_hosts")

        if not os.path.exists(KNOWN_HOSTS_FILE):
            prefix_dir = os.path.dirname(KNOWN_HOSTS_FILE)
            if not os.path.exists(prefix_dir):
                os.makedirs(prefix_dir)
            with open(KNOWN_HOSTS_FILE, "w"):
                pass

        if self.rebuild:
            cmd(["ssh-keygen", "-R", host.name, "-f", KNOWN_HOSTS_FILE])

        ssh_config = []
        # We need to provide a version of the key that doesn't trigger
        # OpenSSHs "wrong permission" check.
        packaged_insecure_key = os.path.join(
            os.path.dirname(__file__), "insecure-private.key"
        )
        local_insecure_key = os.path.abspath("insecure-private.key")
        with open(local_insecure_key, "w") as f_target:
            with open(packaged_insecure_key) as f_packaged:
                f_target.write(f_packaged.read())
        os.chmod(local_insecure_key, 0o600)

        ssh_config.append(
            """
Host {hostname} {aliases}
    HostName {hostname}
    ProxyJump {target_host}
    User developer
    IdentityFile {insecure_private_key}
    StrictHostKeyChecking no
    UserKnownHostsFile {known_hosts}
""".format(
                hostname=host.name,
                aliases=" ".join(host._aliases),
                target_host=self.target_host,
                known_hosts=KNOWN_HOSTS_FILE,
                insecure_private_key=local_insecure_key,
            )
        )

        # More generic includes need to go last because parameters are
        # set by a match-first and things like User settings for * may
        # otherwise collide with our very specific settings. See
        # `man 5 ssh_config`.
        if os.path.exists(os.path.expanduser("~/.ssh/config")):
            ssh_config.append("Host *\n  Include ~/.ssh/config")
        if os.path.exists("ssh_config"):
            ssh_config.append(
                "Host *\n  Include {}".format(os.path.abspath("ssh_config"))
            )

        # Place this in the deployment base directory persistently and
        # keep updating it. This helps users to also interact with containers
        # by running `ssh -F ssh_config_dev mycontainer`
        self.ssh_config_file = os.path.abspath(
            "ssh_config_{}".format(host.environment.name)
        )
        with open(self.ssh_config_file, "w") as f:
            f.write("\n".join(ssh_config))

    def configure_host(self, host, config):
        # Extract provisioning-specific config from host

        # Establish host-specific list of aliases and their public FQDNs.
        host.aliases.update(
            {
                alias.strip(): f"{alias}.{host.name}.{self.target_host}"
                for alias in config.get("provision-aliases", "").strip().split()
            }
        )

        # Development containers have a different internal address for the
        # external aliases so that we need to explicitly override the resolver
        # so that services like nginx can bind to the correct local address.
        try:
            addr = batou.utils.resolve(host.name)
            for alias_fqdn in host.aliases.values():
                output.annotate(
                    f" alias override v4 {alias_fqdn} -> {addr}", debug=True
                )
                batou.utils.resolve_override[alias_fqdn] = addr
        except (OSError, ValueError):
            # We used to catch socket.gaierror here, but reading the
            # docs correctly it can raise any OSError (and socket and gaierror
            # are subclasses)
            pass

        try:
            addr = batou.utils.resolve_v6(host.name)
            for alias_fqdn in host.aliases.values():
                output.annotate(
                    f" alias override v6 {alias_fqdn} -> {addr}", debug=True
                )
                batou.utils.resolve_v6_override[alias_fqdn] = addr
        except (OSError, ValueError):
            # We used to catch socket.gaierror here, but reading the
            # docs correctly it can raise any OSError (and socket and gaierror
            # are subclasses)
            pass

    def summarize(self, host):
        for alias, fqdn in host.aliases.items():
            output.line(f" 🌐 https://{fqdn}/")

    def _initial_provision_env(self, host):
        return NotImplemented

    def provision(self, host):
        self._prepare_ssh(host)

        rsync_path = ""
        if host.environment.service_user:
            rsync_path = (
                f'--rsync-path="sudo -u {host.environment.service_user} '
                f'rsync"'
            )
        env = self._initial_provision_env(host)
        env["SSH_CONFIG"] = self.ssh_config_file
        env["RSYNC_RSH"] = "ssh -F {}".format(self.ssh_config_file)
        if self.rebuild:
            env["PROVISION_REBUILD"] = "1"
        # Add all component variables (uppercased) to the environment
        # $COMPONENT_<component>_<variable>
        # this includes environment overrides and secrets.
        for root_name, root in host.components.items():
            root = root.factory
            for name in dir(root):
                if name.startswith("_"):
                    continue
                if name in ["changed", "workdir", "namevar"]:
                    continue
                value = getattr(root, name)
                if callable(value):
                    continue
                if isinstance(value, property):
                    continue
                key = f"COMPONENT_{root_name}_{name}"
                key = key.upper()
                env[key] = str(value)
            for name, value in host.environment.overrides.get(
                root_name, {}
            ).items():
                key = f"COMPONENT_{root_name}_{name}"
                key = key.upper()
                env[key] = str(value)

        seed_script = ""
        seed_basedir = f"environments/{host.environment.name}"
        seed_script_file = f"{seed_basedir}/provision.sh"
        if os.path.exists(seed_script_file):
            output.annotate(f"    Including {seed_script_file}")
            seed_raw_script = open(seed_script_file).read()
            seed_script += textwrap.dedent(
                f"""\
                # BEGIN CUSTOM SEED SCRIPT
                (
                    cd {seed_basedir}
                    {seed_raw_script}
                )
                # END CUSTOM SEED SCRIPT
                """
            )

        seed_nixos_file = f"environments/{host.environment.name}/provision.nix"
        if (
            os.path.exists(seed_nixos_file)
            and "provision.nix" not in seed_script
        ):
            output.annotate(f"    Including {seed_nixos_file}")
            seed_script = (
                textwrap.dedent(
                    f"""\
                # BEGIN AUTOMATICALLY INCLUDED provision.nix
                (
                    cd {seed_basedir}
                    COPY provision.nix /etc/local/nixos/provision-container.nix
                )
                # END AUTOMATICALLY INCLUDED provision.nix
                """
                )
                + seed_script
            )

        seed_script = seed_script.strip()
        if not seed_script:
            output.annotate(
                f"No provisioning code found in "
                f"environments/{host.environment.name}/provision.nix or "
                f"environments/{host.environment.name}/provision.sh. "
                f"This might be unintentional.",
                yellow=True,
            )

        stdout = stderr = ""
        with tempfile.NamedTemporaryFile(
            mode="w+", prefix="batou-provision", delete=False
        ) as f:
            try:
                os.chmod(f.name, 0o700)
                # We're placing the ENV vars directly in the script because
                # that helps debugging a lot. We need to be careful to delete
                # it later, though, because it is likely to contain secrets.
                f.write(
                    self.SEED_TEMPLATE.format(
                        seed_script=seed_script,
                        rsync_path=rsync_path,
                        ENV=batou.utils.export_environment_variables(env),
                    )
                )
                f.close()
                stdout, stderr = cmd(f.name)
            except Exception:
                raise
            else:
                if "__FC_MANAGE_DEFECT_INDICATOR__" in stdout:
                    stdout = stdout.replace(
                        "__FC_MANAGE_DEFECT_INDICATOR__", ""
                    )
                    output.section(
                        "Errors detected during provisioning", red=True
                    )
                    output.line("STDOUT")
                    output.annotate(stdout)
                    output.line("STDERR")
                    output.annotate(stderr)
                    output.line(
                        "WARNING: Continuing deployment optimistically "
                        "despite provisioning errors. Check errors above this "
                        "line first if encountering subsequent errors.",
                        yellow=True,
                    )
                else:
                    output.line("STDOUT", debug=True)
                    output.annotate(stdout, debug=True)
                    output.line("STDERR", debug=True)
                    output.annotate(stderr, debug=True)
            finally:
                # The script includes secrets so we must be sure that we delete
                # it.
                if output.enable_debug:
                    output.annotate(
                        (
                            f"Not deleting provision script "
                            f"{f.name} in debug mode!"
                        ),
                        red=True,
                    )
                    os.unlink(f.name)


class FCDevContainer(FCDevProvisioner):

    SEED_TEMPLATE = """\
#/bin/sh
set -e

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
    rsync -avz --no-l --safe-links {rsync_path} $what $PROVISION_CONTAINER:$where
}}

if [ ${{PROVISION_REBUILD+x}} ]; then
    ssh $PROVISION_HOST sudo fc-build-dev-container destroy $PROVISION_CONTAINER
fi

ssh $PROVISION_HOST sudo fc-build-dev-container ensure $PROVISION_CONTAINER $PROVISION_CHANNEL "'$PROVISION_ALIASES'"

{seed_script}

# We experimented with hiding errors in this fc-manage run to allow
# partially defective NixOS configurations to be repaired with subsequent
# deployment actions, so we do have to continue here.
# However, we need to show if something goes wrong so that users have an
# indication that the cause might be here. Especially if provisioning
# is half-baked. Unfortunately we cant' decide whether the error is caused
# by the provisioning or the deployment step.

set +e
RUN sudo -i fc-manage -c
result=$?
if [ "$result" -ne "0" ]; then
    echo "__FC_MANAGE_DEFECT_INDICATOR__"
fi

"""  # noqa: E501 line too long
    target_host = None
    channel = None
    aliases = ()

    @classmethod
    def from_config_section(cls, name, section):
        instance = FCDevContainer(name)
        instance.target_host = section["host"]
        instance.channel = section["channel"]
        return instance

    def suggest_name(self, name):
        config = "-F ssh_config" if os.path.exists("ssh_config") else ""
        out, _ = cmd(
            "ssh {config} {target_host} 'nixos-container list'".format(
                config=config, target_host=self.target_host
            )
        )
        names = filter(None, [x.strip() for x in out.splitlines()])
        while True:
            name = uuid.uuid4().hex[:11]
            if name not in names:
                return name

    def _initial_provision_env(self, host):
        return {
            "PROVISION_CONTAINER": host.name,
            "PROVISION_HOST": self.target_host,
            "PROVISION_CHANNEL": self.channel,
            "PROVISION_ALIASES": " ".join(host.aliases.keys()),
        }


class FCDevVM(FCDevProvisioner):

    SEED_TEMPLATE = """\
#/bin/sh
set -e

{ENV}

ECHO() {{
    what=${{1?what to echo}}
    where=${{2?where to echo}}
    RUN "echo $what > $where"
}}

RUN() {{
    cmd=$@
    ssh -F $SSH_CONFIG $PROVISION_VM "$cmd"
}}

COPY() {{
    what=${{1?what to copy}}
    where=${{2?where to copy}}
    rsync -avz --no-l --safe-links {rsync_path} $what $PROVISION_VM:$where
}}

if [ ${{PROVISION_REBUILD+x}} ]; then
    ssh $PROVISION_HOST sudo fc-devhost destroy $PROVISION_VM
fi

ssh $PROVISION_HOST sudo fc-devhost ensure --memory $PROVISION_VM_MEMORY --cpu $PROVISION_VM_CORES --hydra-eval $PROVISION_HYDRA_EVAL --aliases "'$PROVISION_ALIASES'" $PROVISION_VM
{seed_script}

# We experimented with hiding errors in this fc-manage run to allow
# partially defective NixOS configurations to be repaired with subsequent
# deployment actions, so we do have to continue here.
# However, we need to show if something goes wrong so that users have an
# indication that the cause might be here. Especially if provisioning
# is half-baked. Unfortunately we cant' decide whether the error is caused
# by the provisioning or the deployment step.

set +e
RUN sudo -i fc-manage -c
result=$?
if [ "$result" -ne "0" ]; then
    echo "__FC_MANAGE_DEFECT_INDICATOR__"
fi

"""  # noqa: E501 line too long
    target_host = None
    hydra_eval = None
    aliases = ()
    memory = None
    cores = None

    @classmethod
    def from_config_section(cls, name, section):
        instance = FCDevVM(name)
        instance.target_host = section["host"]
        instance.hydra_eval = section["hydra-eval"]
        instance.memory = section.get("memory")
        instance.cores = section.get("cores")
        return instance

    def suggest_name(self, name):
        config = "-F ssh_config" if os.path.exists("ssh_config") else ""
        out, _ = cmd(f"ssh {config} {self.target_host} 'sudo fc-devhost list'")
        names = filter(None, [x.strip() for x in out.splitlines()])
        while True:
            name = uuid.uuid4().hex[:8]
            if name not in names and not name.isnumeric():
                return name

    def _initial_provision_env(self, host):
        env = {
            "PROVISION_VM": host.name,
            "PROVISION_HOST": self.target_host,
            "PROVISION_HYDRA_EVAL": self.hydra_eval,
            "PROVISION_ALIASES": " ".join(host.aliases.keys()),
        }
        if self.memory is not None:
            env["PROVISION_VM_MEMORY"] = self.memory
        if self.cores is not None:
            env["PROVISION_VM_CORES"] = self.cores
        return env
