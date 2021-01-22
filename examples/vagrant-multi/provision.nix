{ config, lib, pkgs, ... }: with config;

{

  swapDevices = [ { device = "/var/swapfile";
                    size = 2048; }];

}
