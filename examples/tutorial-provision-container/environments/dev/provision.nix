{ config, lib, pkgs, modulesPath, ... }: with config;

{

  time.timeZone = lib.mkForce "Europe/Berlin";

  flyingcircus.roles.webgateway.enable = true;
  flyingcircus.roles.redis.enable = true;
  # flyingcircus.roles.percona80.enable = true;
  services.percona.rootPasswordFile = lib.mkForce "/etc/local/nixos/mysql-root-password";
  flyingcircus.roles.postgresql12.enable = true;

  networking.extraHosts = ''
    127.0.0.1 default consul-ext.service.services.vgr.consul.local
    ::1 default consul-ext.service.services.vgr.consul.local
  '';

  # Consul
  services.consul.enable = true;
  services.consul.extraConfig = {
    acl_master_token = "4369DAF2-6D0B-4AC8-BB32-94DE29B7FE1E";
    encrypt = "wrzotzhclj233L4twI/qNrHT+jhGOuXt6UcAQYsfHEY=";
    server = true;
    bootstrap = true;
    datacenter = "services";
    acl_default_policy = "deny";
  };
  #services.consul.interface.bind = "ethsrv";

  environment.systemPackages = [
    pkgs.libffi
    pkgs.cairo
    pkgs.glib
    pkgs.gnome2.pango
    pkgs.fontconfig
  ];

}
