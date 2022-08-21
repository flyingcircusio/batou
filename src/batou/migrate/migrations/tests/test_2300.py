import importlib

import batou
from batou.migrate import output_migration_step

step_2300 = importlib.import_module("batou.migrate.migrations.2300")


def test_2300__migrate__1():
    """It informs about changes in Attribute, Address and secrets."""
    step_2300.migrate(output_migration_step)
    expected = ["Address", "secrets"]
    for term in expected:
        assert term in batou.output.backend.output
