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
  python,
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

    mock
    py
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

  preCheck = ''
    export PYTHONPATH=${py}/${python.sitePackages}:$PYTHONPATH
  '';

  disabledTests = [
    # requires internet access
    "test_manage__2_age"
    "test_manage__reencrypt__1"

    # requires access to /usr/bin/hdiutil
    "test_dmg_extracts_archive_to_target_directory"

    # cannot resolve hosts in sandbox
    "test_address_netloc_attributes"
    "test_address_resolves_listen_address"

    # does not return relative but absolute paths
    # can probably be fixed, then reenabled
    "test_edit_command_loop"
  ];

  disabledTestPaths = [
    # requires internet access for download / pip install
    "src/batou/lib/tests/test_appenv.py"
    "src/batou/lib/tests/test_buildout.py"
    "src/batou/lib/tests/test_download.py"
    "src/batou/lib/tests/test_supervisor.py"

    # bad interpreter `/usr/bin/env python3` in appenv.py
    "src/batou/tests/test_endtoend.py"
  ];

  pname = "batou";
  version = "latest";
  inherit src;
}
