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
        services.openssh.enable = true;
        users.users.serviceuser = {
            isNormalUser = true;
            description = "Service User";
            openssh.authorizedKeys.keys = [
                (builtins.readFile ssh-pubkey)
            ];
        };
      };

    controlhost =
      { ... }:

      {
        users.users.deployinguser = {
          isNormalUser = true;
          description = "Deploying User";
        };

        systemd.services.place-files = {
          description = "Place files for rsyncgit test";
          wantedBy = [ "multi-user.target" ];
          serviceConfig = {
            Type = "oneshot";
            ExecStart = ''
              mkdir -p /home/deployinguser/.ssh
              cp ${ssh-pubkey} /home/deployinguser/.ssh/id_ed25519.pub
              chown deployinguser:deployinguser /home/deployinguser/.ssh/id_ed25519.pub`
              chmod 600 /home/deployinguser/.ssh/id_ed25519.pub
              cp ${ssh-key} /home/deployinguser/.ssh/id_ed25519
              chown deployinguser:deployinguser /home/deployinguser/.ssh/id_ed25519

              mkdir -p /home/deployinguser/batou-src
              chown deployinguser:deployinguser /home/deployinguser/batou-src
              cp -r ${batou-src} /home/deployinguser/batou-src
              chown -R deployinguser:deployinguser /home/deployinguser/batou-src
              chmod -R 700 /home/deployinguser/batou-deployment

            '';
          };
        };
      };


  };

  testScript = ''
    start_all()

    deploytarget.wait_for_unit("sshd", timeout=30);
    controlhost.wait_for_unit("place-files", timeout=30);

    with subtest("can-deploy"):
      controlhost.succeed(
        "sudo -u deployinguser sh -c 'cd /home/deployinguser/batou-src/nix/integration-tests/rsyncgit/batou-deployment && batou deploy targetenv'"
      );

  '';
}
