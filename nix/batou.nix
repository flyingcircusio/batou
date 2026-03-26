{
  lib,
  buildPythonPackage,
  hatchling,
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
  version,
}:
buildPythonPackage {
  pname = "batou";
  inherit version;
  pyproject = true;
  inherit src;

  build-system = [
    hatchling
  ];

  dependencies = [
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
  ];
}
