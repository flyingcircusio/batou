import json
import os
import sys
import textwrap
from unittest import mock

import pytest

from .. import (
    CONFIG_FILE_NAME,
    assert_up_to_date,
    main,
    migrate,
    read_config,
    write_config,
)


def test_migrate__read_config__1(tmp_path):
    """It returns the migration configuration version from ``.batou.json.``."""
    (tmp_path / CONFIG_FILE_NAME).write_text(
        json.dumps({"migration": {"version": 2300}})
    )
    os.chdir(tmp_path)
    assert read_config() == 2300


def test_migrate__read_config__2(tmp_path):
    """It raises a FileNotFoundError if the configuration file is missing."""
    with pytest.raises(FileNotFoundError):
        read_config()


def test_migrate__read_config__3(tmp_path):
    """It raises a KeyError if the configuration file does not have the ...

    right structure.
    """
    (tmp_path / CONFIG_FILE_NAME).write_text(json.dumps({"version": 2300}))
    os.chdir(tmp_path)
    with pytest.raises(KeyError):
        assert read_config()


def test_migrate__read_config__4(tmp_path):
    """It converts the migration version number to an integer."""
    (tmp_path / CONFIG_FILE_NAME).write_text(
        json.dumps({"migration": {"version": "2411"}})
    )
    os.chdir(tmp_path)
    assert read_config() == 2411


@pytest.fixture(scope="function")
def migrations(tmp_path):
    """Create some simple migrations."""
    TEMPLATE = textwrap.dedent(
        """
        def migrate(output):
            pass
    """
    )
    os.chdir(tmp_path)
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").touch()
    migrations = package / "migrations"
    migrations.mkdir()
    (migrations / "__init__.py").touch()
    for step in (2411, 2301, 2300, 2299):
        (migrations / f"{step}.py").write_text(TEMPLATE.format(step))
    sys.path.insert(0, str(tmp_path))
    with mock.patch("batou.migrate.MIGRATION_MODULE", new="package"):
        yield
    sys.path.pop()


def test_migrate__migrate__1(migrations, output):
    """It runs all migration steps starting from next after the ...

    given version.
    """
    assert migrate(2300) == 2411
    assert "Version: 2301\n\nVersion: 2411\n\n" == output.backend.output


def test_migrate__migrate__2(migrations, output):
    """It does nothing if we are already on the latest migration step."""
    assert migrate(2411) == 2411
    assert "" == output.backend.output


def test_migrate__write_config__1(tmp_path):
    """It writes the configuration file."""
    os.chdir(tmp_path)
    write_config(2300)
    assert (tmp_path / CONFIG_FILE_NAME).exists()
    assert read_config() == 2300


def test_migrate__write_config__2(tmp_path):
    """It overwrites an existing the configuration file."""
    os.chdir(tmp_path)
    write_config(2300)
    write_config(2311)
    assert read_config() == 2311


def test_migrate__assert_up_to_date__1(migrations):
    """It returns `True` if the expected version matches the current one."""
    write_config(2411)
    assert assert_up_to_date()


def test_migrate__assert_up_to_date__2(migrations, output):
    """It stops the batou run if the expected version does not match ...

    the current one.
    """
    with pytest.raises(SystemExit):
        assert_up_to_date()
    assert (
        "ERROR: Please run `./batou migrate` first.\n" == output.backend.output
    )


def test_migrate__main__1(tmp_path, migrations, capsys):
    """It runs all migrations if no configuration file is present.

    It creates a configuration file.
    """
    main()
    # We explicitly test the output to the TerminalBackend.
    assert (
        capsys.readouterr().out
        == """\
Current version: 0
Version: 2299

Version: 2300

Version: 2301

Version: 2411

Reached version: 2411
"""
    )
    assert (tmp_path / CONFIG_FILE_NAME).exists()
    assert read_config() == 2411


def test_migrate__main__2(migrations, capsys):
    """It runs no migrations if already at the latest migration step."""
    write_config(2411)
    main()
    # We explicitly test the output to the TerminalBackend.
    assert (
        """\
Current version: 2411
Reached version: 2411
"""
        == capsys.readouterr().out
    )
    assert read_config() == 2411


def test_migrate__main__3(migrations, capsys):
    """It runs no migrations if `bootstrap` is `True` but ...

    sets migration version to current.
    """
    main(bootstrap=True)
    # We explicitly test the output to the TerminalBackend.
    assert "" == capsys.readouterr().out
    assert read_config() == 2411
