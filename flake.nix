{
  description = "A flake for the flyingcircus batou library";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";

    treefmt-nix.url = "github:numtide/treefmt-nix";
    nix-filter.url = "github:numtide/nix-filter";
  };

  outputs = inputs @ {flake-parts, ...}:
    flake-parts.lib.mkFlake {inherit inputs;} {
      imports = [
        inputs.treefmt-nix.flakeModule
      ];

      systems = [
        "x86_64-linux"
        "aarch64-darwin"
      ];

      perSystem = {
        config,
        pkgs,
        ...
      }: let
        src = inputs.nix-filter.lib {
          root = inputs.self;
          exclude = [
            (inputs.nix-filter.lib.matchExt "nix")
            "flake.lock"
          ];
        };
        batou = pkgs.python3Packages.callPackage ./nix/batou.nix {inherit src;};
      in {
        treefmt = {
          projectRootFile = "flake.nix";
          programs.alejandra.enable = true;
          settings.formatter.alejandra.excludes = [
            "src/batou/*"
          ];
          flakeCheck = false;
        };

        formatter = config.treefmt.build.wrapper;

        packages = rec {
          default = batou;
          inherit batou;
        };

        checks = {
          inherit batou;
        };

        devShells.default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps: [batou ps.tox]))
          ];

          shellHook = ''
            export APPENV_BASEDIR=$PWD
          '';
        };
      };
    };
}
