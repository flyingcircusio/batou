#!/bin/sh

set -ex

rm -rf .Python bin lib include
python3.5 -m venv .
ls bin
bin/pip install --upgrade setuptools pip zc.buildout
./bin/buildout
