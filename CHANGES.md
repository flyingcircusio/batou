## Changelog


### 2.0b6 (unreleased)

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
