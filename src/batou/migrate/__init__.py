import importlib
import json
import textwrap

import pkg_resources

from batou._output import TerminalBackend, output

CONFIG_FILE_NAME = '.batou.json'
MIGRATION_MODULE = 'batou.migrate'


def output_migration_step(title: str, text: str) -> None:
    """Print the information of migration step in a formatted way."""
    output.section(title, red=True)
    output.line(textwrap.dedent(text).replace('\n', ''))
    output.line('')


def read_config() -> int:
    """Read the migration configuration file.

    Return the current migration version number.
    Raise a FileNotFoundError in case the migration configuration file is
    missing.
    Raise KeyError if data structure of configuration file is not as expected.
    """
    with open(CONFIG_FILE_NAME) as f:
        return int(json.load(f)['migration']['version'])


def migrate(base_version: int) -> int:
    """Run the migration.

    Return the new migration version number.
    """
    migration_files = pkg_resources.resource_listdir(MIGRATION_MODULE,
                                                     'migrations')
    migration_steps = sorted(
        int(x.partition('.')[0]) for x in migration_files
        if not x.startswith(('_', 'tests')))
    steps = [x for x in migration_steps if x > base_version]
    if not steps:
        return base_version
    for step in steps:
        module = importlib.import_module(
            f'{MIGRATION_MODULE}.migrations.{step}')
        output.tabular('Version', step)
        module.migrate(output_migration_step)
    return step


def write_config(version: int) -> None:
    """Write the version number back the migration configuration file.

    Overwrites already existing configuration file.
    """
    with open(CONFIG_FILE_NAME, 'w') as f:
        json.dump({'migration': {'version': version}}, f)


def main():
    """Run the ``migrate`` batou subcommand."""
    try:
        base_version = read_config()
    except FileNotFoundError:
        base_version = 0
    output.backend = TerminalBackend()
    new_version = migrate(base_version)
    if new_version != base_version:
        write_config(new_version)
