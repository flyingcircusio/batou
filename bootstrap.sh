#!/bin/sh

set -ex

PYTHON=${1:-python3}

rm -rf .Python bin lib include
$PYTHON -m venv .
bin/$PYTHON -m pip install pip
bin/pip install --upgrade setuptools pip zc.buildout
./bin/buildout
