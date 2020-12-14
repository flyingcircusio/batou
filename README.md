<!-- DO NOT EDIT THE README.md FILE. IT IS GENERATED FROM README.md.in AND
     CHANGES.md BECAUSE Github CANNOT DO INCLUDES -->

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
curl -sL https://raw.githubusercontent.com/flyingcircusio/batou/master/bootstrap | sh
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


2.2.2 (2020-12-14)
------------------

- Another brownbag release - connecting to remote hosts was broken
  after refactoring due to missing test coverage. Fixed and 
  added coverage.


2.2.1 (2020-12-14)
------------------

- Fix error reporting that was partially broken in 2.2.


2.2 (2020-12-10)
----------------

- Add `secret files` in addition to secret overrides. Using
  `./batou secrets edit {environment} {example.yaml}` you can
  now create multiple files that are all encrypted using the
  environment's keys.

  To access those secrets you can read them from `environment.secret_files['{example.yaml}']` in your deployment.

  This feature is useful to embed longer data or formats that are
  hard to embed syntactically into the cfg/ini style of the
  main secrets file.

- Fix bug preventing to use `nagios=True` in Supervisor components,
  introduced in batou 2.1.
  ([#98](https://github.com/flyingcircusio/batou/issues/98))

- Make batou compatible with Python 3.9, ie asyncio's `all_tasks`
  has been moved to a new location.
  ([#93](https://github.com/flyingcircusio/batou/issues/93))

- Actually silence SilentConfiguration errors.

- Consider unknown secret overrides (components and attributes)
  to be a configuration error.

2.1 (2020-09-09)
----------------

- Bug 81: provide explicit support for JSON- and YAML-files with
  proper integration to the new diff support and the ability to
  update data through a "dict merge" approach.

- Bug 77: use `ConfigUpdater` so comments are kept when editing secrets.

- Bug 1: provide better error message if remote user does not exist.

  This is also cleaning up the general error output and we're now hiding
  full tracebacks unless batou is run with --debug. People keep complaining
  about traceback output and I agree that it makes things harder to read
  for someone not used to scanning through them quickly.

- Bug 63: provide better error message if GPG is missing.

- Bug 65: don't allow passing undefined namevars or undefined attributes
  to the component constructor. Also prohibit (accidentally) overriding
  methods.

- Bug: zsh compatibility on the remote host was broken with more
  complex sudo mechanism. Added a ZSH workaround.


2.0 (2020-07-15)
----------------

- Ignore directories when verifying archive extractions to avoid
  false non-convergence.


2.0b14 (2020-06-25)
-------------------

- Make sudo properly conditional if we log in directly with the service user,
  but avoid adding a re-connect performance penalty.


2.0b13 (2020-06-25)
-------------------

- Fix git clone when cloning into the component work directory. #27

- Fix binary file handling that broke during 2to3 migration and the test
  was doing the wrong thing.

- Allow marking file content as sensitive, which - for now - will suppress
  diff generation/logging.

- Allow specifying the service_user attribute per host.

- Bugfixes for file components so that verify() is more robust in predictive
  runs.

- Add argument 'predicting' to the `verify()` function signature.
  This argument can be accepted optionally (so we're backwards
  compatible) and will indicate that we're doing a predictive
  run so we can avoid failing when trying to rely on output from
  earlier components.

- Allow the Content component to predict a change based on
  a not-yet-realized source file on the target system.

- Limit parallel connection setup to 5 connections at once. Also, retry
  up to 3 times per connection and stagger retries according to a CSMA/CD
  schema. This helps make connection setup more reliable if using SSH jump
  hosts where many connections may cause sshd's MaxStart to start rejecting
  new connections. (#55)

- Allow adding data-* overrides to host sections in environments' secrets files.

- Reduce AppEnv component directory hashes to 8 byte to avoid the shebang (#!)
  127 character path limit.

- Improve verify() of archive handler so we predict a change if
  something goes wrong (like not having the archive downloaded yet)

- Fix "is supervisor program running" check if it is stopped or exited


2.0b12 (2020-05-13)
-------------------

- Fix broken sort of configuration errors. (#52)


2.0b11 (2020-05-13)
-------------------

- Fix "is supervisord running" check in the Supervisor(enable=False) case


2.0b10 (2020-05-11)
-------------------

- Fix Python 3 compatibility for Debian logrotate component.

- Improve output ordering and formatting. The diffs for predicted (or applied)
  changes now appear in proper order.

- Provide better error messages when batou fails to lock a secret file.

2.0b9 (2020-05-09)
------------------

- Refactor the `appenv` component into smaller components (and move it to `batou.lib.appenv`.

- Always update pip when installing an appenv - this also fixes the Travis tests.


2.0b8 (2020-05-08)
------------------

- Replace 'Deploying <xxx>' with 'Scheduling' as this is only the moment where
  we decide that a component is not blocked by another any longer and can done
  as soon as the worker pool is able to do it. Specifically this means that the
  following output isn't necessarily from this component.

- Mark the hostname for each deployed component in the breadcrumb output
  so that asynchronously deployed components can be visually identified
  correctly.

- Show diff of file changes - both during predict and deployment - to better
  estimate whether template changes are as expected.


2.0b7 (2020-05-07)
------------------

- Update embedded `appenv` to support Python 3.4+.

- Add component `AppEnv` to manage virtualenvs similar to the `appenv` package
  superseding previous virtualenv and buildout components.

- Allow using `assert` statements instead of `batou.UpdateNeeded`.

- Ensure the working directory is the `defdir` during the `configure` phase to
  allow using relative path names.


2.0b6 (2020-04-24)
------------------

- Various smaller fixes to get the remoting code working again.

- Update supervisor to 4.1 and Python 3.

- Allow specifying major versions for virtualenvs (i.e. '2' and '3') to get
  convergence for virtualenvs where we don't control the minor version of the
  targets.

- Add ability to disable supervisor programs.

- Remove '--fast' and '--reset' mode as this isn't needed/ supported by
  appenv at the moment.

- Simplify SSH/sudo and try sudo first. Probably needs further attention once
  we're along the release cycle.

- Fix Python 2.7 virtualenvs - upgrade to latest old-style release of
  `virtualenv`.

### 2.0b5 (2020-04-15)

- Switch to new bootstrapping/self-installing pattern "appenv". See
  `appenv.py` for a work-in-progress schema.


### 2.0b4 (2020-01-13)

- Fix incorrect long->int conversion from 2to3. (Mercurial support)

- Fix brownbag release due to missing support files.


### 2.0b3 (2020-01-10)

- Fix Python3 compatibility for logrotate and crontab

- Add six as dependency, so deployments can be made compatible to both Python 2 and 3 more easy.


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

- The default hash function is now 'sha512', existing deployments
  need to be migrated manually.
