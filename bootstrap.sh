#!/bin/sh

set -ex

PYTHONABS=${1:-python3}
PYTHON=$(basename $PYTHONABS)

rm -rf .Python bin lib include
$PYTHONABS -m venv .
bin/pip install --upgrade setuptools pip zc.buildout
./bin/buildout
