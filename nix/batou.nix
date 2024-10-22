{
  gnupg,
  rsync,
  unzip,
  git,
  subversion,
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
  setuptools,
  jinja2,
  src,
  pytestCheckHook,
  mock,
  pytest-cov,
  pytest-instafail,
  pytest-timeout,
}:
buildPythonPackage {
  build-system = [setuptools];
  dependencies = [
    configupdater
    execnet
    importlib-metadata
    importlib-resources
    jinja2
    py
    pyyaml
    remote-pdb
    requests
  ];

  nativeCheckInputs = [
    pytestCheckHook

    py
    mock
    pytest-cov
    pytest-instafail
    pytest-timeout
    requests

    age
    git
    gnupg
    mercurial
    rsync
    subversion
    unzip
  ];

  PY_IGNORE_IMPORTMISMATCH = 1;

  disabledTests = [
    "test_runs_buildout_successfully"
    "test_runs_buildout3_successfully"
  ];

  disabledTestPaths = [
    "src/batou/lib/tests/test_supervisor.py"
  ];

  pname = "batou";
  version = "latest";
  inherit src;
}
