#!/bin/sh

set -ex

rm -rf .Python bin lib include

$PYTHONABS -m venv .
bin/pip install --upgrade -r requirements.txt

bin/tox -r
