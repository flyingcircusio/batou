{
  config,
  lib,
  pkgs,
  ...
}:
with config; {
  environment.systemPackages = with pkgs; [
    mercurial
  ];

  users.extraUsers = {
    myservice = {
      createHome = true;
      description = "My Service User";
      extraGroups = ["wheel"];
      group = "vagrant";
      home = "/home/myservice";
      shell = "/bin/sh";
      uid = 1234;
    };
  };
}
