#!/bin/sh

# Development environment setup with uv
# Usage: ./develop.sh [python version, default 3.12]

set -ex

python_version="${1:-3.12}"

uv venv --clear --python "python$python_version"
uv sync --all-extras --all-groups

set +x

echo
echo "=== BATOU DEV environment ready ==="
echo 'Run commands with `uv run` prefix or activate with: source .venv/bin/activate'
