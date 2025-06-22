{ pkgs, ... }:
let
  ssh-pubkey = ../../src/batou/secrets/tests/fixture/age/id_ed25519.pub;
  ssh-key = ../../src/batou/secrets/tests/fixture/age/id_ed25519;
  batou-src = ../..;
in
{
  name = "batou-rsync-git";
  nodes = {

    deploytarget =
      { ... }:

      {
        # virtualisation.vlans = [ 1 ];
        # networking.useNetworkd = true;
        # networking.useDHCP = false;
        # systemd.network.networks."01-eth1" = {
        #   name = "eth1";
        #   networkConfig.Address = "10.0.0.1/24";
        # };
        services.openssh.enable = true;
        users.users.serviceuser = {
            isNormalUser = true;
            description = "Service User";
            # openssh.authorizedKeys.keys = [
            #     (builtins.readFile ssh-pubkey)
            # ];
        };
        users.users.deployinguser = {
          isNormalUser = true;
          description = "Deploying User";
          openssh.authorizedKeys.keys = [
              (builtins.readFile ssh-pubkey)
          ];
        };
      };

    controlhost =
      { ... }:

      {
        # virtualisation.vlans = [ 1 ];

        users.users.deployinguser = {
          isNormalUser = true;
          description = "Deploying User";
        };

        networking.hosts = {
          "192.168.1.2" = [ "deploytarget.testdomain" ];
        };

        environment.systemPackages = with pkgs; [
          python3
          git
        ];

        systemd.services.place-files = {
          description = "Place files for rsyncgit test";
          wantedBy = [ "multi-user.target" ];
          serviceConfig = {
            Type = "oneshot";
          };
          script = ''
            mkdir -p /home/deployinguser/.ssh
            chown deployinguser:users /home/deployinguser/.ssh
            chmod 700 /home/deployinguser/.ssh
            cp ${ssh-pubkey} /home/deployinguser/.ssh/id_ed25519.pub
            chown deployinguser:users /home/deployinguser/.ssh/id_ed25519.pub
            chmod 644 /home/deployinguser/.ssh/id_ed25519.pub
            cp ${ssh-key} /home/deployinguser/.ssh/id_ed25519
            chown deployinguser:users /home/deployinguser/.ssh/id_ed25519
            chmod 600 /home/deployinguser/.ssh/id_ed25519

            mkdir -p /home/deployinguser/batou-src
            chown deployinguser:users /home/deployinguser/batou-src
            cp -a ${batou-src}/. /home/deployinguser/batou-src/
            chown -R deployinguser:users /home/deployinguser/batou-src
            chmod -R 700 /home/deployinguser/batou-src
          '';
        };
      };


  };

  testScript = ''
    start_all()

    deploytarget.wait_for_unit("sshd", timeout=30);
    controlhost.sleep(5);
    print(controlhost.systemctl("status place-files"));
    # controlhost.wait_for_unit("place-files", timeout=30);
    def check_finished(_last_try: bool) -> bool:
      state = controlhost.get_unit_property("place-files", "ActiveState", None)
      if state == "inactive":
        return True
      elif state == "active":
        return False
      elif state == "failed":
        raise Exception("place-files failed")
      else:
        return False
    with controlhost.nested("waiting for place-files to finish"):
      retry(check_finished, timeout=900)

    print(controlhost.execute("ls -lah /home/deployinguser/batou-src"));
    print(controlhost.execute("ping 10.0.0.1 -c 1"));
    print(controlhost.execute("ping deploytarget -c 1"));
    print(controlhost.execute("sudo -u deployinguser ssh -vvv deploytarget.testdomain 'echo hello'"));

    with subtest("can-deploy"):
      controlhost.succeed(
        "sudo -u deployinguser sh -c 'cd /home/deployinguser/batou-src/nix/integration-tests/rsyncgit/batou-deployment && git init . && git add . && git config --global user.email ci@example.com && git config --global user.name CI && git commit -m initial'"
      );
      controlhost.succeed(
        "sudo -u deployinguser sh -c 'cd /home/deployinguser/batou-src/nix/integration-tests/rsyncgit/batou-deployment && ./batou deploy targetenv'"
      );

  '';
}
