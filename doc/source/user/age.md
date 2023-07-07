# Documentation for batou secrets with age.

Using batou with age as a secrets backend works similar to using batou with
gpg as before. There is a small format change in the secrets.cfg file, as well
as renaming the secret files from "secret-*" to "secret-*.gpg" or "secret-*.age"
for age encrypted secrets.

You also should set some environment variables to make sure that age is configured
to use the correct keys.

## secrets.cfg.* file

In the secrets.cfg.* file, the `[batou]` section has a new key `secret_provider`.
If that key is not set, batou will use the file extension of the secret file
to determine the secret provider. If the key is set, on saving the secret provider
will be chosen based on the value of the key.

It looks like this:

```ini
[batou]
members =
    https://github.com/user1.keys,
    https://github.com/user2.keys
secret_provider = age
```

You can see that using the `age` secret provider allows us to specify keys from
https sources. This is because age accepts ssh public keys as encryption recipients.

We accept ssh public keys (beginning with `ssh-`) as well as age public keys
(beginning with `age1-`), or `http(s)://` urls to ssh public-key files.

GPG is still supported as before.

On saving a file with changes, the `secret_provider` key will be added to the
secrets.cfg file. If you do not change the file, the file will not even be re-encrypted.

## Moving a project to the new secrets format

Essentially, you just have to rename the secret files from `secret-*` to `secret-*.gpg`
as well as renaming the `secrets.cfg` file to `secrets.cfg.gpg`.

You can also use the script in `rename-secrets.py` to do this for you.

## New environment variables

Age needs to know which secret key to use for decryption. Set the `BATOU_AGE_IDENTITIES`
key to your ssh private key file, or a comma separated list of ssh private key files to
try to use for decryption.

By default, batou will use the search order of ssh
(~/.ssh/id_rsa, ~/.ssh/id_ecdsa, ~/.ssh/id_ecdsa_sk,
~/.ssh/id_ed25519, ~/.ssh/id_ed25519_sk and ~/.ssh/id_dsa).

You can run this in your shell or add it to your `.bashrc` or `.zshrc` file:

```bash
export BATOU_AGE_IDENTITIES=$HOME/.ssh/id_ed25519
```

If your ssh key is encrypted, you can use the `BATOU_AGE_IDENTITY_PASSPHRASE` environment
variable to provide a 1password reference url to your ssh key passphrase.

```bash
export BATOU_AGE_IDENTITY_PASSPHRASE="op://<vault>/<item>[/<section>]/<field>"
```

You can find the secret reference url in the 1password 8 app, by right clicking on the
arrow next to the password field and selecting "Copy Secret Reference". Follow the
[1password documentation](https://developer.1password.com/docs/cli/secret-references/#step-1-copy-secret-references) for more information.

You need to set up the 1password cli to use the `op` command. See the
[1password cli documentation](https://developer.1password.com/docs/cli/get-started/).

If you do not set the `BATOU_AGE_IDENTITY_PASSPHRASE` environment variable, you will
be prompted for the passphrase on every run of batou that uses age.

## Changes in the project exposed API

No changes
