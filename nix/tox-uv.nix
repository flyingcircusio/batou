{
  lib,
  buildPythonPackage,
  fetchFromGitHub,
  hatchling,
  hatch-vcs,
  tox,
  uv,
}:

buildPythonPackage rec {
  pname = "tox-uv";
  version = "1.33.4";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "tox-dev";
    repo = "tox-uv";
    tag = version;
    hash = "sha256-aiQUCP2/Gw1jQ636Rr3EFizs0EW/abPKAohbl+v19Fo=";
  };

  build-system = [
    hatchling
    hatch-vcs
  ];

  dependencies = [
    tox
  ];

  # Relax version constraints - nixpkgs versions are close enough
  pythonRelaxDeps = [ "tox" "packaging" ];

  # uv binary needs to be in PATH
  makeWrapperArgs = [
    "--prefix PATH : ${lib.makeBinPath [ uv ]}"
  ];

  pythonImportsCheck = [ "tox_uv" ];

  meta = {
    description = "Integration of uv with tox";
    homepage = "https://github.com/tox-dev/tox-uv";
    license = lib.licenses.mit;
  };
}
