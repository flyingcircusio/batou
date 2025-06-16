import json
import os
import os.path
import tempfile
import textwrap
import uuid

import requests

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


class FCDevVM(Provisioner):

    target_host = None
    aliases = ()
    memory = None
    cores = None

    hydra_eval = ""  # deprecated
    channel_url = ""
    image_url = ""

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
    ssh -F $SSH_CONFIG $PROVISION_VM "{ssh_cmd_prefix} $cmd"
}}

COPY() {{
    what=${{1?what to copy}}
    where=${{2?where to copy}}
    rsync -avz --no-owner --no-group --no-links --safe-links {rsync_path} $what $PROVISION_VM:$where
}}

if [ ${{PROVISION_REBUILD+x}} ]; then
    ssh $PROVISION_HOST sudo fc-devhost destroy $PROVISION_VM
fi

cli_args="--memory $PROVISION_VM_MEMORY\\
  --cpu $PROVISION_VM_CORES \\
  --aliases \\"'$PROVISION_ALIASES'\\""

# Error handling is done in the python part
if [ -n "$PROVISION_HYDRA_EVAL" ]; then
    cli_args="${{cli_args}} --hydra-eval $PROVISION_HYDRA_EVAL"
else
    cli_args="${{cli_args}} --image-url $PROVISION_IMAGE --channel-url $PROVISION_CHANNEL"
fi

ssh $PROVISION_HOST sudo fc-devhost ensure \\
    $cli_args \\
    $PROVISION_VM

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

    def __init__(self, name):
        super().__init__(name)
        self._known_ssh_hosts = {}

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

        self._known_ssh_hosts[host.name] = (
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

        # Gather all known hosts together - otherwise we can only access
        # one provisioned host per environment.
        for section in self._known_ssh_hosts.values():
            ssh_config.append(section)

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
        return {
            "PROVISION_VM": host.name,
            "PROVISION_HOST": self.target_host,
            "PROVISION_ALIASES": " ".join(host.aliases.keys()),
            "PROVISION_HYDRA_EVAL": self.hydra_eval,
            "PROVISION_CHANNEL": self.channel_url,
            "PROVISION_IMAGE": self.image_url,
            "PROVISION_VM_MEMORY": self.memory,
            "PROVISION_VM_CORES": self.cores,
        }

    def provision(self, host):
        self._prepare_ssh(host)

        rsync_path = ""
        if host.environment.service_user:
            user_prefix = f"sudo -u {host.environment.service_user}"
            ssh_cmd_prefix = user_prefix
            rsync_path = f'--rsync-path="{user_prefix} rsync"'

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
                        ssh_cmd_prefix=ssh_cmd_prefix,
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

        # Retrieve the VM information from the remote side.
        vm_info, _ = cmd(
            f"ssh {self.target_host} cat /etc/devhost/vm-configs/{host.name}.json"
        )
        host._provision_info = json.loads(vm_info)
        # Seed our resolver overrides for the deployment name and the real name
        # so that all other hosts can see either when using the `Address` utility
        # API, independent of specific DNS situations during bootstrapping.
        for alias in host._aliases + [host.name]:
            batou.utils.resolve_override[alias] = host._provision_info["srv-ip"]

    @classmethod
    def from_config_section(cls, name, section):
        instance = FCDevVM(name)
        instance.target_host = section["host"]
        instance.memory = section["memory"]
        instance.cores = section["cores"]

        if "release" in section:
            resp = requests.get(section["release"])
            resp.raise_for_status()
            release_info = resp.json()
            instance.channel_url = release_info["channel_url"]
            instance.image_url = release_info["devhost_image_url"]
        elif "hydra-eval" in section:
            instance.hydra_eval = section["hydra-eval"]
        else:
            raise ValueError(
                "Either `release` or `hydra-eval` must be set in the provisioner config section."
            )
        return instance

    def suggest_name(self, name):
        config = "-F ssh_config" if os.path.exists("ssh_config") else ""
        out, _ = cmd(f"ssh {config} {self.target_host} 'sudo fc-devhost list'")
        names = filter(None, [x.strip() for x in out.splitlines()])
        while True:
            name = uuid.uuid4().hex[:8]
            if name not in names and not name.isnumeric():
                return name
