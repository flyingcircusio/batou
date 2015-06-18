{ config, lib, pkgs, ... }: with config;

{

    environment.systemPackages = with pkgs; [
        mercurial
    ];
  
}
