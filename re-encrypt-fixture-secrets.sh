#!/bin/sh

base=$PWD
alias encrypt="gpg --homedir ${base}/src/batou/secrets/tests/fixture/gnupg -e --yes -r 03C7E67FC9FD9364"

cd ${base}/src/batou/secrets/tests/fixture
encrypt -o encrypted.cfg.gpg cleartext.cfg

cd ${base}/examples/errors
encrypt -o environments/errors/secrets.cfg.gpg secrets.cfg.clear

cd ${base}/examples/errors2
encrypt -o environments/errors/secrets.cfg.gpg secrets.cfg.clear

cd ${base}/examples/tutorial-secrets
encrypt -o environments/tutorial/secrets.cfg.gpg tutorial-secrets.cfg.clear
encrypt -o environments/tutorial/secret-foobar.yaml.gpg tutorial-foobar.yaml.clear
encrypt -o environments/gocept/secrets.cfg.gpg gocept-secrets.cfg.clear
