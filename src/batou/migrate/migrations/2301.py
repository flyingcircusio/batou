from pathlib import Path


def migrate(output):
    """Move secrets to environments."""
    output(
        "New environments structure",
        """
        Each environment is now a directory containing all the configuration
        files: The unencrypted configuration is now stored in `environment.cfg`
        whereas the encrypted one is stored in `secrets.cfg`. The previous
        `secrets` directory is no more. Additional encrypted files are now in
        the directory of the environment they belong to. Their names are now
        prefixed with `secret-` instead of the name of the environment they
        belong to. **Please note:** This migration step is done automatically.
        You just have to check-in the changes to the version control system.""",
    )
    environments = _get_environment_names()
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
