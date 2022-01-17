## Changelog


2.3b4 (unreleased)
------------------

### Features

- Add a migration framework. Automatic migrations can now be called using
  `batou migrate`.
  ([#185](https://github.com/flyingcircusio/batou/issues/185))

- Allow to pin the `pip` version used in the `Buildout` component.
  ([#263](https://github.com/flyingcircusio/batou/issues/263))

- Automatically migrate environments and secrets to the new structure using
  `./batou migrate`.
  ([#185](https://github.com/flyingcircusio/batou/issues/185))


2.3b3 (2021-11-30)
------------------

### Action needed

- Require defaults to be explicitly declared for `Attribute`.
  ([#237](https://github.com/flyingcircusio/batou/issues/237))

### Bug fixes

- Ignore hostmap entries for hosts that have changed their dynamic hostname
  settings to false.

### Features

- Automatically pick up `provision.sh` and/or `provision.nix`.

  You do not need to explicitly define a COPY command to copy the
  `provision.nix` to the container, but if you do then we avoid doing it
  twice.

- Warn if neither `provision.nix` nor provision.sh are given as that seems more
  of an accident (like misspelling the filenames).

- Continue deployments on failure when running `fc-manage` during provisioning
  but be more explicit about errors and warn the user that something maybe be
  fishy in the deployment subsequently.

- Use different colors for success depending on whether you ran a real
  deployment, a consistency check, or a predition.
  (https://github.com/flyingcircusio/batou/issues/209)


2.3b2 (2021-10-05)
------------------

### Action needed

- Fail if an attribute is set both in environment and via secrets.
  ([#28](https://github.com/flyingcircusio/batou/issues/28))

- Avoid implicit conversion of Attribute defaults. In cases where the default
  value should be converted, use `default_conf_string`. This may result in
  some changes if your code relied on this implicit conversion. If you use
  `batou_ext`, update to a current commit..
  ([#89](https://github.com/flyingcircusio/batou/issues/89))

- Raise an error if an internet protocol family is used but not configured.
  ([#189](https://github.com/flyingcircusio/batou/issues/189))

### Bug fixes

- Fix Python 3 compatibility with some Mercurial-based batou repositories.

- Adapt `bootstrap.sh` to the use of appenv.

### Features

- Integrate `remote-pdb` to debug batou runs.
  ([#199](https://github.com/flyingcircusio/batou/issues/199))

- NetLoc objects are now comparable.
  ([#88](https://github.com/flyingcircusio/batou/issues/88))

- Enhance file `Mode` objects to accept integers, octal mode strings
  and 'rwx' strings as the `mode` argument. This allows homogenous use
  in Python code and overrides through config files.
  ([#61](https://github.com/flyingcircusio/batou/issues/61))

- Do not render diffs for files which contain contents of `secrets/*`.
  ([#91](https://github.com/flyingcircusio/batou/issues/91))

- Assure that `requirements.lock` is build with the oldest supported Python
  version to keep it consistent – newer Python versions have included some
  packages in standard library which older ones need as dependencies.
  ([#145](https://github.com/flyingcircusio/batou/issues/145))

- Remove default option for installation via `pip`.
  ([#212](https://github.com/flyingcircusio/batou/issues/212))

- Implement dynamic, pluggable provisioning of hosts.

  We provide a built-in plugin to support NixOS development containers
  that feel similar to the Flying Circus VM platform.

### Other changes

- Improve error message for DNS lookup semantics.

- Render a better error message if gpg failed to decrypt a secrets file.
  ([#123](https://github.com/flyingcircusio/batou/issues/123))

- Raise exception when calling `batou secrets add` or `batou secrets remove`
  with an unknown environment name.
  ([#143](https://github.com/flyingcircusio/batou/issues/143))

- Render an error message if `batou secrets summary` fails during decryption.
  ([#165](https://github.com/flyingcircusio/batou/issues/165))

- Do not write secrets files without recipient.
  ([#184](https://github.com/flyingcircusio/batou/issues/184))

2.3b1 (2021-05-21)
------------------

- Drop support for Python 3.5. (#114)

- batou.lib.buildout: Enable support for Buildout 3 by allowing
  to specify a `wheel` package version to install in the
  virtualenv. (#148)

- Fix bootstrapping projects with the new appenv structure. Vendor
  an appenv version to ensure lockstep compatibility.

- Fix consistency check semantics: we accidentally performed
  actual deployments during consistency checks.

- Fix rsync repository mode to capture deleted top-level elements
  in the source.

- Improve DNS lookup semantics.

  We experienced two major problems with the current code:

  1. IPv6 lookups were done opportunistically and thus if DNS issues happened
  during deployments we would suddenly drop IPv6 support instead of failing.

  2. There was no logging to find out why the code was making specific decisions
  and to see what the underlying network APIs were returning. We now provide
  detailed debug logs for analyzing DNS issues.

  There were slight adjustments in the internal API (resolve/resolve_v6) that
  should be backwards compatible.

  The public API reflects a more strict stance now:

  - by default we only look up IPv4

  - you can explicitly set the `require_v6` and `require_v4` options for
    `Address` objects. batou will then perform the required lookups (or not)
    and it will be a hard failure if required lookups can not be performed.

  We recommend to adjust those parameters on Address objects depending on your
  environment, e.g. if you want IPv6 in production but not in Vagrant.


2.2.4 (2021-02-11)
------------------

- Repair `File(group=)`, it now works just like `File(owner=)`

- Remove debugging code from secrets editing which caused encryption errors to crash and loose unsaved edits. (#139)

- Fix shipping of deployment code with git-bundle when using a
  branch. Before the entire branch history was uploaded with each
  deployment to each host (#131)

- Allow specifying a custom pip version in `AppEnv`.

2.2.3 (2021-01-20)
------------------

- Fix #124: notifications crashed when trying to display environment names
  but used environment objects.


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
