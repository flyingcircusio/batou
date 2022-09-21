from pathlib import Path


def migrate(output):
    """Move secrets to environments."""
    output(
        "Environments have separate directories now",
        """

Each environment has been turned into a separate directory containing all the
configuration files:

* unencrypted configuration is now stored in
  `environments/<env>/environment.cfg`
* encrypted configuration is now stored in `environments/<env>/secrets.cfg`
* additional encrypted files are stored in `environments/<env>/secret-*`

The old `secrets` directory is now gone.

All data was migrated automatically for you, but you will need to commit those
changes manually.

        """,
        "automatic",
    )
    environments = _get_environment_names()
    # sort environments by length to ensure that we migrate the most specific
    # environments first
    environments.sort(key=len, reverse=True)
    for name in environments:
        _migrate_environment(name)


def _get_environment_names():
    return [
        x.stem
        for x in (Path.cwd() / "environments").iterdir()
        if x.suffix == ".cfg"
    ]


def _migrate_environment(name: str) -> None:
    cwd = Path.cwd()
    environments = cwd / "environments"
    (environments / name).mkdir(exist_ok=True)
    (environments / f"{name}.cfg").rename(
        environments / name / "environment.cfg"
    )
    secrets_file = cwd / "secrets" / f"{name}.cfg"
    if secrets_file.exists():
        secrets_file.rename(environments / name / "secrets.cfg")
    try:
        for secrets_file in (cwd / "secrets").glob(f"{name}-*"):
            secrets_file.rename(
                environments
                / name
                / secrets_file.name.replace(f"{name}-", "secret-", 1)
            )
    except FileNotFoundError:
        pass
