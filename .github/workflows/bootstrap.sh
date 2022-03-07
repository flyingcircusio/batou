#/usr/bin/env bash
# Sample as shown in https://batou.readthedocs.io/en/stable/user/install.html#starting-a-new-batou-project
set -x
mkdir myproject
cd myproject
git init
curl -sL https://raw.githubusercontent.com/flyingcircusio/batou/master/bootstrap | sh
