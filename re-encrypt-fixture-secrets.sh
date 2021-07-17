#!/bin/sh

base=$PWD
alias encrypt="gpg --homedir ${base}/src/batou/secrets/tests/fixture/gnupg -e --yes -r 03C7E67FC9FD9364  -r 306151601E813A47"

cd ${base}/src/batou/secrets/tests/fixture
encrypt -o encrypted.cfg cleartext.cfg

cd ${base}/examples/errors/secrets
encrypt -o errors.cfg errors.cfg.clear




