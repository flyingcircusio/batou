#!/bin/sh

set -ex

rm -rf .Python bin lib include .tox examples/*/.appenv

python3 -m venv .
bin/pip install --upgrade -r requirements-dev.txt
