from pathlib import Path


def migrate(output):
    """Rename secret files to match new naming scheme."""
    output(
        "Secrets may be encrypted with age or gpg now",
        """

The two secret providers `age` and `gpg` signify their encryption method in the
file name. The new naming scheme is:
secrets.cfg -> secrets.cfg.gpg
secret-foo -> secret-foo.gpg

Since previously all secrets were encrypted with gpg, we rename all files to
match the new naming scheme. This is done automatically for you, but you will
need to commit those changes manually.

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
    secrets_cfg = cwd / "secrets" / f"{name}.cfg"
    if secrets_cfg.exists():
        secrets_cfg.rename(environments / name / "secrets.cfg.gpg")
    for secret_file in (cwd / "secrets").glob(f"secret-*"):
        filename = str(secret_file.name)
        secret_file.rename(environments / name / (filename + ".gpg"))
