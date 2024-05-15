{
  buildPythonPackage,
  fetchPypi,
  markupsafe,
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
}:
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
    ];

    pname = "batou";
    version = "latest";
    inherit src;
  }
