{
  buildPythonPackage,
  requests,
  pyyaml,
  execnet,
  importlib-metadata,
  importlib-resources,
  remote-pdb,
  py,
  configupdater,
  mock,
  pytest,
  setuptools,
  jinja2,
  src,
  bcrypt,
  cryptography,
  rustPlatform,
  fetchFromGitHub,
  cargo,
  rustc,
  setuptools-rust,
}: let
  pyrage = buildPythonPackage rec {
    pname = "pyrage";
    version = "1.2.3";

    src = fetchFromGitHub {
      owner = "woodruffw";
      repo = pname;
      rev = "v${version}";
      hash = "sha256-asTdmH+W+tmoUMIwmmGC13j+HdTeZL8Th27pvsy7TT0=";
    };

    cargoDeps = rustPlatform.fetchCargoTarball {
      inherit src;
      name = "${pname}-${version}";
      hash = "sha256-F8NG8H3Nt5FinuTWdBR8/aSj+Pvin/J/AvgQHL3qknE=";
    };

    format = "pyproject";

    nativeBuildInputs = [
      cargo
      rustPlatform.cargoSetupHook
      rustPlatform.maturinBuildHook
      rustc
      setuptools-rust
    ];
  };
in
  buildPythonPackage {
    propagatedBuildInputs = [
      requests
      pyyaml
      execnet
      importlib-metadata
      importlib-resources
      remote-pdb
      py
      configupdater
      mock
      pytest
      setuptools
      jinja2
      bcrypt
      cryptography
      pyrage
    ];

    pname = "batou";
    version = "latest";
    inherit src;
  }
