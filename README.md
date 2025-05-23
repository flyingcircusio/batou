<img width="150" src="https://batou.readthedocs.io/en/latest/_static/batou.png">

batou helps you to automate your application deployments:

* You create a model of your deployment using a simple but powerful Python API.
* You configure how the model applies to hosts in different environments.
* You verify and run the deployment with the batou utility.

Getting started with a new project is easy:

```console
mkdir myproject
cd myproject
git init
curl -sL https://raw.githubusercontent.com/flyingcircusio/batou/main/bootstrap | sh
git commit -m "Start a batou project."
```

Here's a minimal application model:

```console
$ mkdir -p components/myapp
$ cat > components/myapp/component.py
from batou.component import Component
from batou.lib.python import VirtualEnv, Package
from batou.lib.supervisor import Program

class MyApp(Component):

    def configure(self):
        venv = VirtualEnv('2.7')
        self += venv
        venv += Package('myapp')
        self += Program('myapp',
            command='bin/myapp')
```

And here's a minimal environment:

```console
$ mkdir environments
$ cat > environments/dev/environment.cfg
[environment]
connect_method = local

[hosts]
localhost = myapp
```

To deploy this, you run:

```console
$ ./batou deploy dev
```

Check the [detailed documentation](http://batou.readthedocs.org) to get going with a more ambitious project.


## Features

* Separate your application model from environments
* Supports idempotent operation for incremental deployments
* Deploy to multiple hosts simultaneously
* Automated dependency resolution for multi-host scenarios
* No runtime requirements on your application
* Encrypted secrets with multiple access levels: store your
  SSL certificates, SSH keys, service secrets and more to get true 1-button deployments.
* Deploy to local machines, Vagrant, or any SSH host
* Broad SSH feature support by using OpenSSH through execnet
* Only few dependencies required on the remote host
* Ships with a library of components for regularly needed tasks
* self-bootstrapping and self-updating - no additional scripting needed

## License

The project is licensed under the 2-clause BSD license.

## Hacking

* Make sure `mercurial` and `subversion` are installed and in `$PATH`.
* Run `./develop.sh` to create a local virtualenv with everything set up.
* Run the test suite using: `bin/tox`
* Build the documentation using: `cd doc; make`
* Set up GPG for the examples with `export GNUPGHOME=<DIRECTORY OF BATOU HERE>/src/batou/secrets/tests/fixture/gnupg`
* Make sure [age](https://github.com/FiloSottile/age) is installed and in `$PATH` for age encryption support.

## Development and release process

* Changes should be accompanied with a changelog entry. Use `./changelog.sh` to create one.
* Releasing will create a tag and publishes the package to pypi. Use `./release-this.sh` to create a release.

## Changelog

See [CHANGES.md](./CHANGES.md).
