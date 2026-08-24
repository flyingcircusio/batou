#!/bin/sh
#
# Regenerate the GPG test fixtures:
#
#   - Create two new, never-expiring fixture keys:
#       ct@example.com  (RSA 2048, sign + encryption subkey)
#       cz@example.com  (Ed25519/Cv25519, sign + encryption subkey)
#   - ct signs cz's key; both keys carry ultimate ownertrust (mirroring
#     the historical fixture), so unattended batch encryption works.
#   - Export the fixture keyring (public keys for both identities,
#     secret key for ct only) to src/batou/secrets/tests/fixture/gnupg/
#   - Re-encrypt all encrypted fixture/example secret files.
#   - Rewrite the referenced key IDs in the repository, including in
#     this script itself, so it can simply be run again at any time.
#
# Run from the repository root.

set -eu

base=$PWD
fixture=$base/src/batou/secrets/tests/fixture
gnupg=$fixture/gnupg

if [ ! -f "$gnupg/pubring.gpg" ]; then
    echo "Please run from the repository root." >&2
    exit 1
fi

# Key IDs currently referenced in the repository; updated below.
CT_KEYID_OLD="8D58FCFB"
CZ_KEYID_OLD="41F5816A"

tmp=$(mktemp -d)
chmod 700 "$tmp"
trap 'GNUPGHOME="$tmp" gpgconf --kill gpg-agent >/dev/null 2>&1; rm -rf "$tmp"' EXIT

keyid_of() {
    # homedir uid -> last 8 chars of the primary key fingerprint
    gpg --homedir "$1" --list-keys --with-colons "$2" \
        | awk -F: '$1 == "fpr" { print $10; exit }' \
        | cut -c33-40
}

echo "Generating fixture keys ..."
cat > "$tmp/ct.keygen" <<EOF
%no-protection
Key-Type: RSA
Key-Length: 2048
Key-Usage: sign
Subkey-Type: RSA
Subkey-Length: 2048
Subkey-Usage: encrypt
Name-Real: batou (unit test)
Name-Email: ct@example.com
Expire-Date: 0
%commit
EOF
gpg --homedir "$tmp" --batch --generate-key "$tmp/ct.keygen"

cat > "$tmp/cz.keygen" <<EOF
%no-protection
Key-Type: eddsa
Key-Curve: Ed25519
Key-Usage: sign
Subkey-Type: ecdh
Subkey-Curve: Cv25519
Subkey-Usage: encrypt
Name-Real: batou (unit test 2)
Name-Email: cz@example.com
Expire-Date: 0
%commit
EOF
gpg --homedir "$tmp" --batch --generate-key "$tmp/cz.keygen"

echo "Signing cz's key with ct's key ..."
gpg --homedir "$tmp" --batch --yes \
    --local-user ct@example.com --sign-key cz@example.com

CT_KEYID=$(keyid_of "$tmp" ct@example.com)
CZ_KEYID=$(keyid_of "$tmp" cz@example.com)
echo "New key IDs: ct=$CT_KEYID cz=$CZ_KEYID"

echo "Rewriting key IDs in repository files ..."
replace_keyid() { # old new file
    sed "s/$1/$2/g" "$3" > "$3.tmp" && mv "$3.tmp" "$3"
}
for f in \
    examples/errors/secrets.cfg.clear \
    src/batou/secrets/tests/test_manage.py \
    "$0"
do
    replace_keyid "$CT_KEYID_OLD" "$CT_KEYID" "$f"
    replace_keyid "$CZ_KEYID_OLD" "$CZ_KEYID" "$f"
done

echo "Re-encrypting fixture and example secrets ..."
encrypt() { # cleartext output
    gpg --homedir "$tmp" --batch --yes --trust-model always \
        --encrypt --recipient ct@example.com --recipient cz@example.com \
        --output "$2" "$1"
}
encrypt "$fixture/cleartext.cfg" "$fixture/encrypted.cfg.gpg"
encrypt "$base/examples/errors/secrets.cfg.clear" \
    "$base/examples/errors/environments/errors/secrets.cfg.gpg"
encrypt "$base/examples/errors2/secrets.cfg.clear" \
    "$base/examples/errors2/environments/errors/secrets.cfg.gpg"
encrypt "$base/examples/errors2/secretserror-secrets.cfg.clear" \
    "$base/examples/errors2/environments/secretserror/secrets.cfg.gpg"
encrypt "$base/examples/tutorial-secrets/tutorial-secrets.cfg.clear" \
    "$base/examples/tutorial-secrets/environments/tutorial/secrets.cfg.gpg"
encrypt "$base/examples/tutorial-secrets/tutorial-foobar.yaml.clear" \
    "$base/examples/tutorial-secrets/environments/tutorial/secret-foobar.yaml.gpg"
encrypt "$base/examples/tutorial-secrets/gocept-secrets.cfg.clear" \
    "$base/examples/tutorial-secrets/environments/gocept/secrets.cfg.gpg"
encrypt "$base/examples/tutorial-secrets/tutorial-foobar.yaml.clear" \
    "$base/examples/tutorial-secrets/environments/gocept/secret-foobar.yaml.gpg"

echo "Exporting fixture keyring ..."
gpg --homedir "$tmp" --export ct@example.com cz@example.com > "$gnupg/pubring.gpg"
gpg --homedir "$tmp" --export-secret-keys ct@example.com > "$gnupg/secring.gpg"

GNUPGHOME="$tmp" gpgconf --kill gpg-agent >/dev/null 2>&1
cp "$tmp/trustdb.gpg" "$gnupg/trustdb.gpg"

echo "Cleaning up runtime artifacts ..."
rm -rf "$gnupg/private-keys-v1.d" "$gnupg/random_seed" "$gnupg/crls.d" \
    "$gnupg/.gpg-v21-migrated" "$gnupg/pubring.gpg~"
rm -f "$gnupg"/S.*

echo "Done."
