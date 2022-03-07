#/usr/bin/env bash
# Sample as shown in https://batou.readthedocs.io/en/stable/user/install.html#starting-a-new-batou-project
set -ex
base=$(cwd)
mkdir myproject
cd myproject
git init
# Extract current bootstrap command from the docs.
grep  "bootstrap | sh" $base/doc/source/user/install.txt | sed -e  's/\$//' | sh
