
{ pkgs ? (import <nixpkgs> {})
, lib ? pkgs.lib
, stdenv ? pkgs.stdenv
}:

let

  pkgs_17_09_src = pkgs.fetchFromGitHub {
    owner = "nixos";
    repo = "nixpkgs";
    rev = "df8e85f22f2bd1550e1ba5afc38935bf25d81cda";
    sha256 = "13dkg38pwd13j7vwhpvpp0wlr7mdkd415g1zflkd2baf8v4xhn0s";
  };
  pkgs_17_09 = import pkgs_17_09_src {};

in 
stdenv.mkDerivation rec {
  name = "python";

  # Customizable development requirements
  buildInputs = [
    (with pkgs_17_09; pkgs.callPackage ./nix/python26 { })
    pkgs_17_09.python27
    pkgs_17_09.python35
    pkgs_17_09.python36
  ];

  # Customizable development shell setup with at last SSL certs set
  shellHook = ''
    export SSL_CERT_FILE=${pkgs_17_09.cacert}/etc/ssl/certs/ca-bundle.crt
  '';
}

