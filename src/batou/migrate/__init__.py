import importlib
import json
import textwrap
from typing import List

import importlib_resources

from batou._output import TerminalBackend, output

CONFIG_FILE_NAME = ".batou.json"
MIGRATION_MODULE = "batou.migrate"


def output_migration_step(
    title: str, text: str, status: str = "manual"
) -> None:
    """Print the information of migration step in a formatted way."""
    if status == "manual":
        label = "🔧"
        args = {"yellow": True}
    elif status == "automatic":
        label = "✅"
        args = {"green": True}
    output.annotate(f"{label} {title}", **args)
    output.line("")
    output.line(textwrap.dedent(text).strip())
    output.line("")


def read_config() -> int:
    """Read the migration configuration file.

    Return the current migration version number.
    Raise a FileNotFoundError in case the migration configuration file is
    missing.
    Raise KeyError if data structure of configuration file is not as expected.
    """
    with open(CONFIG_FILE_NAME) as f:
        return int(json.load(f)["migration"]["version"])


def get_migration_steps() -> List[int]:
    """Return the sorted list of all known migration steps."""
    migration_files = (
        importlib_resources.files(MIGRATION_MODULE)
        .joinpath("migrations")
        .iterdir()
    )
    migration_files = [x.name for x in migration_files]
    return sorted(
        int(x.partition(".")[0])
        for x in migration_files
        if not x.startswith(("_", "tests"))
    )


def migrate(base_version: int) -> int:
    """Run the migration.

    Return the new migration version number.
    """
    steps = [x for x in get_migration_steps() if x > base_version]
    if not steps:
        return base_version
    for step in steps:
        module = importlib.import_module(
            f"{MIGRATION_MODULE}.migrations.{step}"
        )
        output.annotate(f"Version: {step}", bold=True)
        output.line("")
        module.migrate(output_migration_step)
    return step


def write_config(version: int) -> None:
    """Write the version number back the migration configuration file.

    Overwrites already existing configuration file.
    """
    with open(CONFIG_FILE_NAME, "w") as f:
        json.dump({"migration": {"version": version}}, f)
        f.write("\n")


def get_current_version() -> int:
    """Get the version number stored in the configuration file.

    Return `0` if there is no configuration file.
    """
    try:
        version = read_config()
    except FileNotFoundError:
        version = 0
    return version


def get_expected_version() -> int:
    """Get the highest version number deduced from migration files."""
    return get_migration_steps()[-1]


def assert_up_to_date() -> bool:
    """Assert that the current migration version matches the expected one."""
    if get_current_version() == get_expected_version():
        return True
    output.error("Please run `./batou migrate` first.")
    raise SystemExit(-153)


def main(*, bootstrap: bool = False) -> None:
    """Run the ``migrate`` batou subcommand."""
    if bootstrap:
        write_config(get_expected_version())
        return
    output.backend = TerminalBackend()
    base_version = get_current_version()
    output.annotate(f"Current version: {base_version}", bold=True)
    new_version = migrate(base_version)
    if new_version != base_version:
        write_config(new_version)
    output.annotate(f"Reached version: {new_version}", bold=True, green=True)
