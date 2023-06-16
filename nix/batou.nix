{
  buildPythonPackage,
  fetchPypi,
  markupsafe,
  requests,
  pyyaml,
  execnet,
  importlib-metadata,
  remote-pdb,
  py,
  configupdater,
  mock,
  pytest,
  setuptools,
  src,
}: let
  jinja2 = buildPythonPackage rec {
    pname = "Jinja2";
    version = "3.0.1";
    propagatedBuildInputs = [markupsafe];
    src = fetchPypi {
      inherit pname version;
      sha256 = "sha256-cD9IS0emr1AudDyRIllcyBKwJx9mFyJAMRT3GnnQ9aQ=";
    };
  };
in
  buildPythonPackage {
    propagatedBuildInputs = [
      requests
      pyyaml
      execnet
      importlib-metadata
      remote-pdb
      py
      configupdater
      mock
      pytest
      setuptools
      jinja2
    ];

    pname = "batou";
    version = "latest";
    inherit src;
  }
