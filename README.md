<!-- DO NOT EDIT THE README.md FILE. IT IS GENERATED FROM README.md.in AND
     CHANGES.md BECAUSE Github CANNOT DO INCLUDES -->

<p align="right">
    <a href="https://travis-ci.org/flyingcircusio/batou"><img title="Current Build Status" src="https://travis-ci.org/flyingcircusio/batou.svg?branch=master"></a>
</p>

<img width="150" src="https://batou.readthedocs.io/en/latest/_static/batou.png">

batou helps you to automate your application deployments:

* You create a model of your deployment using a simple but powerful Python API.
* You configure how the model applies to hosts in different environments.
* You verify and run the deployment with the batou utility.

Getting started with a new project is easy:

```console
$ mkdir myproject
$ cd myproject
$ curl https://bitbucket.org/flyingcircus/batou/raw/tip/src/batou/bootstrap-template -o batou
$ chmod +x batou
$ ./batou
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
$ cat > environments/dev.cfg
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
* Automated dependency resolution for multi-host
  scenarios
* No runtime requirements on your application
* Encrypted secrets with multiple access levels: store your
  SSL certificates, SSH keys, service secrets and more to get true 1-button deployments.
* Deploy to local machines, Vagrant, or any SSH host
* Broad SSH feature support by using OpenSSH through execnet
* Only few dependencies required on the remote host
* Ships with a library of components for regularly needed
  tasks
* self-bootstrapping and self-updating - no additional
  scripting needed

## License

The project is licensed under the 2-clause BSD license.
## Changelog


### 2.0b3 (unreleased)

- Improve error message in case of a DNS error during address resolution


### 2.0b2 (2019-10-15)

#### General

- Make encryption/decryption error prompt more readable.

- Fix coding style issues.

#### Features

- Add coarse grained parallelization of deployments.

  Using asyncio we now schedule rooot components for deployment as soon as all
  their dependencies are completed. However, due to execnet being synchronous
  this only has a visible effect for components on  multiple hosts. This will
  speed up long running multi-host deployments.

  In the future this will become more fine-grained so that we can even deploy
  multiple independent components on the same host in parallel.

#### Bugs

- Fix issue #5: allow using % in secrets similar to regular overrides.

- Fix secrets editing, add test coverage for the affected code.

#### Testing

- Relax global pytest timeouts to avoid slow network failures.

- Switch from broken/abandoned pytest-codecheckers to pytest-flake8

- Enable flake8, remove unused pytest markers.

- Fix warnings

- Make warnings errors.

#### Build system / Development environment

- Update example batou scripts

- Fix travis build environments. Support Python 3.5, 3.6, 3.7, 3.8-dev and
  nightly (also 3.8 currently).

- Generalize development bootstrapping code for dual use in local and travis environments.


### 2.0b1 (2019-10-11)

- Drop support for Python 2.

- Move to Python 3.5+.

  A smooth migration mechanism may become available in the future
  based on users' needs.

- The default hash function is now 'sha256', existing deployments
  need to be migrated manually.
