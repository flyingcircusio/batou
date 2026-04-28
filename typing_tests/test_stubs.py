"""Type-level tests for batou stubs.

Checked with mypy / ty / basedpyright. Never executed at runtime.

STATUS:
  - cmd() overloads: mypy ✅ ty ✅ basedpyright ❌ (ignores overloads)
  - Attribute[T] descriptor: none of the three checkers support
    `name: str = Attribute(str)`. The annotation and descriptor clash.
    This is a known limitation — see mypy#15710.
  - Attribute() call with various defaults: mypy ✅ ty ✅
"""

from __future__ import annotations

import subprocess
from typing import assert_type

from batou.component import Attribute, Component, ConfigString
from batou.utils import cmd

# =============================================================================
# cmd() overloads — batou.utils
# =============================================================================

# communicate=True (default) → tuple[str, str]
stdout, stderr = cmd("echo hello")
assert_type(stdout, str)
assert_type(stderr, str)

# communicate=True explicit → tuple[str, str]
result = cmd("echo hello", communicate=True)
assert_type(result, tuple[str, str])

# communicate=False → Popen[str]
proc = cmd("long-running-task", communicate=False)
assert_type(proc, subprocess.Popen[str])

# List-form command
out, err = cmd(["ls", "-la"])
assert_type(out, str)


# =============================================================================
# Component.cmd() overloads
# =============================================================================


class CmdComponent(Component):
    def verify(self) -> None:
        stdout, stderr = self.cmd("echo hello")
        assert_type(stdout, str)
        assert_type(stderr, str)

    def update(self) -> None:
        result = self.cmd("echo hello", communicate=True)
        assert_type(result, tuple[str, str])

    def spawn(self) -> None:
        proc = self.cmd("long-running-task", communicate=False)
        assert_type(proc, subprocess.Popen[str])


# =============================================================================
# Attribute() constructor — should accept all variant signatures
# =============================================================================

# These are class-level assignments WITHOUT annotation — all checkers accept
# this because there's no annotation to conflict with.


class AttributeDefaults(Component):
    # String type with string default
    name = Attribute(str, default="test")
    # String type with ConfigString default (expand+conversion at runtime)
    greeting = Attribute(str, default=ConfigString("hello {{component.name}}"))
    # String type with None default (optional)
    label = Attribute(str, default=None)
    # Int type with int default
    port = Attribute(int, default=8080)
    # Bool type with literal conversion
    debug = Attribute("literal", default=False)
    # List type with list default — mypy can't infer T from string conversion
    tags = Attribute("list", default=[])  # type: ignore[var-annotated]
    # No default — required attribute
    required = Attribute(str)


# =============================================================================
# KNOWN LIMITATIONS (documented for reference, not tested)
# =============================================================================

# 1. `name: str = Attribute(str)` — annotation+descriptor clash.
#    All three checkers reject this because Attribute[str] is not
#    assignable to str at the class level. The __set_name__ + __get__
#    descriptor protocol is not understood in combination with annotations.
#
# 2. basedpyright ignores @overload on cmd() — sees the runtime signature
#    `Popen[bytes] | tuple[str|bytes, str|bytes]` instead of our overloads.
#    Likely because basedpyright prioritizes the .py source over .pyi stubs.
#
# 3. `Attribute("list")` — mypy infers T=Never for string conversions
#    because it can't resolve the string literal to a type. ty handles
#    this better with Unknown.
