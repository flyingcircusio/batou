#!/bin/bash
set -euo pipefail

cd $(dirname $0)

mkdir -p CHANGES.d
exec uv run scriv create --edit
