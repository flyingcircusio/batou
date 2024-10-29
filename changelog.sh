#!/bin/sh

set -ex

cd $(dirname $0)
chmod u+w bin/*ctivate* || true
python3 -m venv .
bin/pip install scriv

mkdir -p CHANGES.d
exec bin/scriv create --edit
