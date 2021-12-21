#!/bin/sh

base=$PWD
alias encrypt="gpg --homedir ${base}/src/batou/secrets/tests/fixture/gnupg -e --yes -r 03C7E67FC9FD9364  -r 306151601E813A47"

cd ${base}/src/batou/secrets/tests/fixture
encrypt -o encrypted.cfg cleartext.cfg

cd ${base}/examples/errors
encrypt -o environments/errors/secrets.cfg secrets.cfg.clear

cd ${base}/examples/errors2
encrypt -o environments/errors/secrets.cfg secrets.cfg.clear

cd ${base}/examples/tutorial-secrets
encrypt -o environments/tutorial/secrets.cfg tutorial-secrets.cfg.clear
encrypt -o environments/tutorial/secret-foobar.yaml tutorial-foobar.yaml.clear
encrypt -o environments/gocept/secrets.cfg gocept-secrets.cfg.clear
