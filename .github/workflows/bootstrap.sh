#/usr/bin/env bash
# Sample as shown in https://batou.readthedocs.io/en/stable/user/install.html#starting-a-new-batou-project
set -ex
base=$(pwd)
mkdir myproject
cd myproject
git init
cat $base/bootstrap | sh
