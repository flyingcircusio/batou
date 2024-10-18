{
  gnupg,
  rsync,
  unzip,
  git,
  subversion,
  python3,
  age,
  mercurial,
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

  checkPhase = ''
    tox -e py
    cp report.xml $out
    cp -r htmlcov $out
  '';

  nativeCheckInputs = [
    (python3.withPackages (ps: [ps.tox]))
    mercurial
    age
    git
    subversion
    unzip
    rsync
    gnupg
  ];

  pname = "batou";
  version = "latest";
  inherit src;
}
