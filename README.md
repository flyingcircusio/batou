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
* Run the test suite using: `uv run tox`
* Build the documentation using: `cd doc; make`
* Set up GPG for the examples with `export GNUPGHOME=<DIRECTORY OF BATOU HERE>/src/batou/secrets/tests/fixture/gnupg`
* Make sure [age](https://github.com/FiloSottile/age) is installed and in `$PATH` for age encryption support.

### Typed development

batou is typed on two layers: `src/batou` carries the inline annotations of the
package itself, while `stubs/` is a standalone stub package released in lockstep
with batou that provides type information to deployments on top of the released
batou package — see [stubs/README.md](stubs/README.md).

Each type checker simulates exactly one Python version; together they span the
supported 3.10-3.14 window (runtime compatibility is the test matrix's job, not
the typing gates'):

* `ty` — src, examples and typing_tests at Python 3.14 (`ty.toml`); also runs as two pre-commit hooks.
* `mypy` — stubs and typing_tests at Python 3.14 (`[tool.mypy]`). The `stubs` tox env sets `MYPYPATH=stubs` so `batou` resolves through the stubs; it additionally lints the `.pyi` files (ruff, flake8-pyi) and runs `stubtest`, which checks the stubs against the actual package at runtime (`stubs/stubtest-allowlist.txt` lists accepted deviations). For matching results outside tox, export `MYPYPATH=$PWD/stubs` first.
* `basedpyright` — full scope (src, stubs, typing_tests, examples) at Python 3.10 (`pyrightconfig.json`); known diagnostics are baselined in `.basedpyright/baseline.json` and new ones fail the gate.

Run all static gates via `uv run tox -e stubs,typing,basedpyright`.

Shrink the baseline after fixing diagnostics: `uv run --group typing basedpyright --writebaseline` — the end-of-file-fixer pre-commit hook then adds a trailing newline; re-stage the file.

Editor: point the interpreter at the project `.venv`. Zed ships both `ty` and `basedpyright`, but as of November 2026 `basedpyright` is the default Python server — switch with `"language_servers": ["!basedpyright", "ty"]` in your Zed settings to get ty's verdict. VS Code (basedpyright extension) and Neovim (nvim-lspconfig) read `pyrightconfig.json` including the baseline; Pylance does not — it will show diagnostics that the CI accepts. PyCharm reads neither `ty.toml` nor `pyrightconfig.json` — use the tox gates.

## Development and release process

* Changes should be accompanied with a changelog entry. Use `./changelog.sh` to create one.
* Releasing will create a tag and publishes the package to pypi. Use `./release-this.sh` to create a release.

## Changelog

See [CHANGES.md](./CHANGES.md).
