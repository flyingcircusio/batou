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
    for name in _get_environment_names():
        _migrate_environment(name)


def _get_environment_names():
    return [x for x in (Path.cwd() / "environments").iterdir() if x.is_dir()]


def _migrate_environment(name: str) -> None:
    cwd = Path.cwd()
    environment_dir = cwd / "environments" / name
    secrets_cfg = environment_dir / f"secrets.cfg"
    if secrets_cfg.exists():
        secrets_cfg.rename(str(secrets_cfg) + ".gpg")
        for secret_file in environment_dir.iterdir():
            if secret_file.name.startswith(
                "secret-"
            ) and not secret_file.name.endswith(".gpg"):
                secret_file.rename(str(secret_file) + ".gpg")
