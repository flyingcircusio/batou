#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2020 Flying Circus
"""
appenv - a single-file tool that pins Python packages to exact versions and
         exposes their binaries via symlinks. Drop into a repository, commit,
         and every checkout gets the same tools at the same versions.

Important assumptions:

  - Python 3.9+
  - pyproject.toml next to the appenv file
  - system has usable uv (see UV_MIN_VERSION) or uv can be installed on-demand
  - the appenv file is placed in a repo with the name of the application
"""

from __future__ import annotations

__version__ = "2026.6.30"

import argparse
import difflib
import io
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from argparse import Namespace
from dataclasses import dataclass, replace
from functools import cached_property
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Final, NamedTuple, NoReturn
from urllib.parse import urlsplit, urlunsplit

# Global logger instance
log = logging.getLogger("appenv")

# Exit codes (BSD sysexits.h conventions) — meaning per constant is the single
# source of truth; docs/dev/index.md Exit Codes table mirrors this.
EXIT_CODE_DATAERR = 65  # Input data was correct but could not be processed
EXIT_CODE_NOINPUT = 67  # Required input file missing (e.g. pyproject.toml)
EXIT_CODE_UNAVAILABLE = 68  # Required resource (binary, Python) not found
EXIT_CODE_USAGE = 64  # Invalid arguments or malformed input

# Format constants
MAX_HELP_TEXT_LENGTH = 50
VERSION_PARTS_COUNT = 3


class GroupedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Group subcommands by category in help output.

    Inherits from :class:`argparse.RawDescriptionHelpFormatter` so the
    parser description keeps its literal newlines (the ``\\n\\n`` between
    the version banner and the description). ``HelpFormatter`` would
    collapse all whitespace to single spaces, merging the version line
    with the description into one paragraph.
    """

    def _format_action(self, action: argparse.Action) -> str:
        groups = (
            ("Project", ["init", "migrate", "self-update", "update-lockfile"]),
            ("Venv", ["prepare", "reset"]),
            ("Tools", ["python", "run", "uv"]),
            ("Debug", ["version"]),
        )

        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            # Build command -> help mapping from _choices_actions
            cmd_help = {ca.metavar: ca.help or "" for ca in action._choices_actions}  # noqa: SLF001

            # Build grouped subcommand list
            lines = []
            for group_name, commands in groups:
                lines.append(f"  {group_name}:")
                for cmd in commands:
                    if cmd in action.choices:
                        help_text = cmd_help.get(cmd, "")
                        # Truncate long help texts
                        if len(help_text) > MAX_HELP_TEXT_LENGTH:
                            help_text = help_text[:47] + "..."
                        lines.append(f"    {cmd:<16}  {help_text}")
                lines.append("")  # Empty line between groups

            # Remove trailing empty line and return
            return "\n".join(lines).rstrip() + "\n"

        return super()._format_action(action)


class UsageArgumentParser(argparse.ArgumentParser):
    """ArgumentParser that exits with EXIT_CODE_USAGE (64) on usage errors.

    argparse defaults to exit code 2 for invalid choices and missing required
    arguments, but appenv documents 64 (EXIT_CODE_USAGE) for all usage errors
    (see docs/user/commands.md). Overriding ``error()`` on the main parser also
    covers every subparser: ``add_subparsers`` defaults ``parser_class`` to
    ``type(self)``, so subcommands inherit this override automatically. The
    ``--version`` action (which calls ``self.exit(0)``) is unaffected.
    """

    def error(self, message: str) -> NoReturn:
        log.error("argparse-usage-error: prog=%s message=%s", self.prog, message)
        # Mirror argparse's own error(): usage line + "<prog>: error: <message>",
        # only with EXIT_CODE_USAGE instead of the default 2.
        self.print_usage(sys.stderr)
        self.exit(EXIT_CODE_USAGE, f"{self.prog}: error: {message}\n")


class IndexEntry(NamedTuple):
    """A ``[[tool.uv.index]]`` entry migrated from a pip index option.

    ``url`` is always credential-free: the literal secret is stripped before
    this object is constructed and never reaches pyproject.toml or stdout.
    """

    name: str
    url: str
    has_credentials: bool


# ---------------------------------------------------------------------------
# pip requirements.txt option handling
#
# pip stores repository configuration as inline options in requirements.txt.
# uv has no concept of most of them, so appenv separates them at migrate time:
# index/extra-index URLs become [[tool.uv.index]] entries; everything else that
# has no pyproject.toml equivalent is dropped with a warning.
# ---------------------------------------------------------------------------

# Options that carry an index URL -> mapped to a [[tool.uv.index]] entry.
_PIP_INDEX_URL_OPTIONS: Final = frozenset({"--index-url", "--extra-index-url"})

# Options that take a value (``--opt value`` or ``--opt=value``) but have no
# pyproject.toml equivalent -> dropped, reported once by option name.
_PIP_DROPPED_VALUE_OPTIONS: Final = frozenset(
    {"--hash", "--find-links", "--trusted-host", "--no-binary", "--only-binary"}
)

# Flag options (no value) with no pyproject.toml equivalent -> dropped.
_PIP_DROPPED_FLAG_OPTIONS: Final = frozenset({"--require-hashes", "--pre"})


class RequirementsTxtInfo(NamedTuple):
    dependencies: list[str]
    editable_dependencies: list[str]
    python_versions: list[str]
    indexes: list[IndexEntry]
    skipped_options: list[str]


def _split_pip_option_token(token: str) -> tuple[str, str | None]:
    """Split a ``--option[=value]`` token into ``(name, value_or_None)``."""
    name, sep, value = token.partition("=")
    return name, value if sep else None


def _strip_index_url_credentials(url: str) -> tuple[str, bool]:
    """Return ``(clean_url, has_credentials)`` for a pip index URL.

    Strips any ``user:password@`` userinfo so the literal secret can never
    reach pyproject.toml. A credential-free URL is returned verbatim so it
    round-trips exactly (e.g. ``==`` against the original holds).

    Works on the raw netloc string rather than :class:`urllib.parse.SplitResult`
    properties, which raise ``ValueError`` on malformed ports.
    """
    parts = urlsplit(url)
    netloc = parts.netloc
    if "@" not in netloc:
        return url, False
    userinfo, _, hostpart = netloc.rpartition("@")
    clean_netloc = hostpart
    clean = urlunsplit(
        (parts.scheme, clean_netloc, parts.path, parts.query, parts.fragment)
    )
    return clean, bool(userinfo.strip())


def _uv_index_env_token(name: str) -> str:
    """uv env-var token for an index name: uppercase, non-alnum -> ``_``.

    ``UV_INDEX_<NAME>_USERNAME`` / ``_PASSWORD`` per
    https://docs.astral.sh/uv/concepts/indexes/#authentication
    """
    return re.sub(r"[^A-Z0-9]", "_", name.upper())


def _index_name_from_url(url: str, used_names: set[str]) -> str:
    """Derive a unique, uv-compatible index name from the URL host.

    The host is collapsed to ``[A-Za-z0-9-]`` so it doubles as a stable
    ``UV_INDEX_<NAME>`` token; duplicates are disambiguated with a suffix.
    """
    host = urlsplit(url).hostname or "index"
    base = re.sub(r"[^A-Za-z0-9]+", "-", host).strip("-") or "index"
    candidate = base
    suffix = 1
    while candidate in used_names:
        suffix += 1
        candidate = f"{base}-{suffix}"
    used_names.add(candidate)
    return candidate


def _build_index_entries(raw_urls: list[str]) -> list[IndexEntry]:
    """Build de-duplicated, credential-free index entries from raw URLs.

    Duplicate URLs (after credential stripping) collapse to one entry, matching
    pip's own de-duplication of repeated ``--extra-index-url`` lines.
    """
    entries: list[IndexEntry] = []
    used_names: set[str] = set()
    seen_urls: set[str] = set()
    for raw in raw_urls:
        clean, has_credentials = _strip_index_url_credentials(raw)
        if clean in seen_urls:
            continue
        seen_urls.add(clean)
        entries.append(
            IndexEntry(
                name=_index_name_from_url(clean, used_names),
                url=clean,
                has_credentials=has_credentials,
            )
        )
    return entries


def _consume_next_value(
    tokens: list[str], i: int, *, guard_non_option: bool
) -> tuple[str | None, int]:
    """Consume the token after position ``i`` as an option value.

    Returns ``(value_or_None, next_i)``: ``next_i`` advances past the consumed
    token, or stays at ``i`` when there is no following token, or — for unknown
    options that may themselves be flags — when the following token is an
    option and ``guard_non_option`` is set.
    """
    n = len(tokens)
    if i + 1 >= n:
        return None, i
    if guard_non_option and tokens[i + 1].startswith("-"):
        return None, i
    return tokens[i + 1], i + 1


def _apply_pip_option(
    name: str,
    inline: str | None,
    tokens: list[str],
    i: int,
    index_urls: list[str],
    skipped: list[str],
) -> int:
    """Handle one pip-option at ``tokens[i]``; return the updated index.

    Index-URL options append to ``index_urls``; dropped options append to
    ``skipped``. An inline ``--opt=val`` form satisfies value-bearing options
    without consuming the next token.
    """
    if name in _PIP_INDEX_URL_OPTIONS:
        url = inline
        if not url:
            url, i = _consume_next_value(tokens, i, guard_non_option=False)
        if url:
            index_urls.append(url)
    elif name in _PIP_DROPPED_VALUE_OPTIONS:
        skipped.append(name)
        if inline is None:
            _, i = _consume_next_value(tokens, i, guard_non_option=False)
    elif name in _PIP_DROPPED_FLAG_OPTIONS:
        skipped.append(name)
    else:
        # Unknown option: never let it become a dependency, and consume a
        # likely value token so it does not leak in as a dep either.
        skipped.append(name)
        if inline is None:
            _, i = _consume_next_value(tokens, i, guard_non_option=True)
    return i


def _parse_requirement_line(
    line: str,
) -> tuple[str | None, list[str], list[str]]:
    """Parse one requirements.txt line into ``(dep, index_urls, skipped)``.

    ``dep`` is the dependency with all inline pip-options removed, or ``None``
    when the line carried only options. ``index_urls`` are raw index URLs
    (credentials stripped later, collectively). ``skipped`` lists each dropped
    option by name (may contain duplicates across ``--hash`` repeats).
    """
    tokens = line.split()
    dep_tokens: list[str] = []
    index_urls: list[str] = []
    skipped: list[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        token = tokens[i]
        if token.startswith("-") and token not in ("-", "--"):
            name, inline = _split_pip_option_token(token)
            i = _apply_pip_option(name, inline, tokens, i, index_urls, skipped)
        else:
            dep_tokens.append(token)
        i += 1
    return (" ".join(dep_tokens) if dep_tokens else None, index_urls, skipped)


# PEP 508 normalized project name: starts and ends with [A-Z0-9], middle may
# contain [A-Z0-9._-]. Used by :func:`_is_likely_valid_pep508_dep` as a cheap
# pre-filter — full PEP 508 parsing (extras, markers, URLs) stays uv's job.
_PEP_508_NAME_RE = re.compile(
    r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$", re.IGNORECASE
)


def _is_likely_valid_pep508_dep(dep: str) -> bool:
    """Cheap heuristic: does ``dep`` look like a valid PEP 508 requirement?

    SPEC: migrate-pep508-validation::pre-filter

    appenv ships zero runtime deps, so this can't use ``packaging``. It
    accepts two forms and rejects everything else so uv does not produce a
    confusing setuptools traceback at ``uv lock`` time:

    1. URL requirements: ``name @ url`` (with surrounding whitespace) or bare
       VCS URLs (``git+https://``, ``hg+``, ``svn+``, ``bzr+``).
    2. Named requirements: the leading token (terminated by whitespace,
       ``[`` extras, version-specifier operators ``<>=!~``, ``;`` marker, or
       ``@`` URL) matches PEP 508's project-name pattern. The remainder is
       ignored — authoritative parsing remains uv's job at lock time.
    """
    dep = dep.strip()
    if not dep:
        return False
    if " @ " in dep or dep.startswith(("git+", "hg+", "svn+", "bzr+")):
        return True
    if re.match(r"^https?://|^file:", dep, re.IGNORECASE):
        return True
    name = re.match(r"^[^\s\[<>=!~;@]+", dep)
    return bool(name) and bool(_PEP_508_NAME_RE.match(name.group(0)))


def convert_version_preference(versions: list[str]) -> tuple[str, list[str]]:
    """Convert version list to requires-python specifier.

    Returns (specifier, missing_versions) where missing_versions
    are versions in the range that weren't explicitly listed.

    Example: ["3.11", "3.13", "3.10"] -> (">=3.10,<3.14", ["3.12"])
    """
    if not versions:
        return ">=3.10", []

    sorted_v = sorted(versions, key=lambda v: tuple(map(int, v.split("."))))
    min_v = sorted_v[0]
    max_v = sorted_v[-1]

    # Increment minor for exclusive upper bound
    parts = max_v.split(".")
    next_minor = f"{parts[0]}.{int(parts[1]) + 1}"

    # Find gaps in range
    min_parts = tuple(map(int, min_v.split(".")))
    max_parts = tuple(map(int, max_v.split(".")))
    all_in_range = [
        f"{min_parts[0]}.{i}" for i in range(min_parts[1], max_parts[1] + 1)
    ]
    missing = [v for v in all_in_range if v not in versions]

    return f">={min_v},<{next_minor}", missing


def _validate_python_version(value: str) -> str:
    """argparse ``type=`` validator for ``--python-version``.

    Accepts only ``major.minor`` strings (e.g. ``3.13``). Raising
    :class:`argparse.ArgumentTypeError` routes through
    :meth:`UsageArgumentParser.error`, which exits :data:`EXIT_CODE_USAGE`
    (64) before :func:`create_pyproject` writes anything — no minimum is
    enforced, only the format.
    """
    if not re.fullmatch(r"\d+\.\d+", value):
        msg = f"expected a 'major.minor' version like '3.13', got {value!r}"
        raise argparse.ArgumentTypeError(msg)
    return value


def _dedup_preserve_order(items: list[str]) -> list[str]:
    """Return a new list with duplicates removed, preserving first-seen order.

    SPEC: fix-init-safety-layer::dedup-deps — used to canonicalize
    ``--dep`` repeats before they reach ``pyproject.toml``.
    """
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def version_satisfies_constraints(
    version: str, min_version: str, max_version: str | None = None
) -> bool:
    ver_parts = [int(p) for p in version.split(".")]
    min_parts = [int(p) for p in min_version.split(".")]

    if ver_parts < min_parts:
        return False

    if max_version is not None:
        max_parts = [int(p) for p in max_version.split(".")]
        if ver_parts >= max_parts:
            return False

    return True


def remove_path(path: Path) -> None:
    """Remove a path regardless of type (symlink, file, or directory).

    Logs the type before removal for debugging purposes.
    """
    if path.is_symlink():
        log.debug("removing-path: type=symlink path=%s", path)
        path.unlink()
    elif path.is_file():
        log.debug("removing-path: type=file path=%s", path)
        path.unlink()
    elif path.is_dir():
        log.debug("removing-path: type=directory path=%s", path)
        shutil.rmtree(path)


class Pyproject:
    """Encapsulates pyproject.toml parsing, migration, and generation."""

    def __init__(self, base: Path) -> None:
        self.path = base / "pyproject.toml"
        self.requirements_path = base / "requirements.txt"

    @cached_property
    def content(self) -> str:
        if not self.exists:
            return ""
        return self.path.read_text()

    def migrate_from_requirements_txt(self) -> Pyproject:
        req_info = self.requirements_txt_info

        requires_python, missing = convert_version_preference(req_info.python_versions)
        content = self._generate_content_with_project(
            project_name=self.path.parent.name,
            description="Migrated Appenv project",
            dependencies=req_info.dependencies,
            requires_python=requires_python,
            indexes=req_info.indexes,
        )
        self.path.write_text(content)

        # Print info about missing versions
        if missing:
            log.info("migration-missing-versions: missing=%s", missing)
            print(f"Note: Versions {', '.join(missing)} were not in preference list")

        return Pyproject(self.path.parent)

    @property
    def requires_python(self) -> tuple[str | None, str | None]:
        """Parse requires-python from pyproject.toml.

        Returns tuple of (min_version, max_version) where max may be None.
        """
        if not self.exists:
            return (None, None)

        # Extract the requires-python value
        value_match = re.search(
            r'requires-python\s*=\s*["\']([^"\']+)["\']', self.content
        )
        if not value_match:
            return (None, None)

        spec = value_match.group(1)

        # Parse minimum version (>=X.Y or >X.Y)
        min_match = re.search(r">=?\s*(\d+\.\d+)", spec)
        min_version = min_match.group(1) if min_match else None

        # Parse maximum version (<X.Y or <=X.Y)
        max_match = re.search(r"<=?\s*(\d+\.\d+)", spec)
        max_version = max_match.group(1) if max_match else None

        return (min_version, max_version)

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @cached_property
    def has_project_section(self) -> bool:
        """Check if TOML content has a [project] section."""
        for line in self.content.splitlines():
            stripped = line.strip()
            if stripped == "[project]" or stripped.startswith("[project."):
                return True
        return False

    @property
    def can_be_created_from_requirements_txt(self) -> bool:
        return not self.has_project_section and self.requirements_path.exists()

    @cached_property
    def requirements_txt_info(self) -> RequirementsTxtInfo:
        return self._parse_requirements_file()

    def print_migration_info(self) -> None:
        req_info = self.requirements_txt_info

        if req_info.skipped_options:
            log.warning(
                "migration-pip-options-skipped: options=%s",
                ", ".join(req_info.skipped_options),
            )
            print(
                "Warning: unsupported pip options have no pyproject.toml "
                "equivalent and were dropped:"
            )
            for option in req_info.skipped_options:
                print(f"  - {option}")
            print()

        for index in req_info.indexes:
            if not index.has_credentials:
                log.info(
                    "migration-index-added: name=%s url=%s credentials=false",
                    index.name,
                    index.url,
                )
                continue
            token = _uv_index_env_token(index.name)
            log.warning(
                "migration-index-credentials-stripped: name=%s url=%s "
                "env_username=UV_INDEX_%s_USERNAME env_password=UV_INDEX_%s_PASSWORD",
                index.name,
                index.url,
                token,
                token,
            )
            print(
                f"Warning: index '{index.name}' had embedded credentials in "
                f"requirements.txt. They are NOT stored in pyproject.toml."
            )
            print(
                f"Provide them via environment variables "
                f"UV_INDEX_{token}_USERNAME and UV_INDEX_{token}_PASSWORD "
                f"(or a ~/.netrc entry for {index.url})."
            )
            print()

        if req_info.editable_dependencies:
            log.warning(
                "migration-editable-skipped: count=%d specs=%s",
                len(req_info.editable_dependencies),
                ", ".join(req_info.editable_dependencies),
            )
            print(
                f"Warning: {len(req_info.editable_dependencies)} "
                f"editable install(s) skipped:"
            )
            for spec in req_info.editable_dependencies:
                print(f"  - {spec}")
            print("Add them manually to pyproject.toml if needed.\n")

        if req_info.python_versions and len(req_info.python_versions) > 1:
            print(f"Found python preference: {', '.join(req_info.python_versions)}")
            print(f"Using minimum version: {req_info.python_versions[0]}\n")

        print(
            f"Found {len(req_info.dependencies)} dependency(ies): "
            f"{', '.join(req_info.dependencies)}"
        )

    def _parse_requirements_file(self) -> RequirementsTxtInfo:
        """Parse requirements.txt into dependencies, indexes, and skipped options.

        pip-options (``--index-url``, ``--hash``, ...) are separated from real
        dependencies so they never leak into ``[project] dependencies`` as
        invalid PEP 508 specifiers. Index URLs become :class:`IndexEntry`
        objects (credentials stripped); unsupported options are recorded in
        ``skipped_options`` for the migrate warning.
        """
        log.debug("parse-requirements-file: path=%s", self.requirements_path)
        content = self.requirements_path.read_text()
        raw_lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        editable_specs = [line for line in raw_lines if line.startswith("-e ")]

        dependencies: list[str] = []
        raw_index_urls: list[str] = []
        skipped: list[str] = []
        for line in raw_lines:
            if line.startswith("-e "):
                continue
            dep, index_urls, line_skipped = _parse_requirement_line(line)
            if dep:
                dependencies.append(dep)
            raw_index_urls.extend(index_urls)
            skipped.extend(line_skipped)

        indexes = _build_index_entries(raw_index_urls)

        if skipped:
            # De-duplicate while preserving first-seen order for a stable warning.
            deduped: list[str] = []
            seen: set[str] = set()
            for option in skipped:
                if option not in seen:
                    seen.add(option)
                    deduped.append(option)
            skipped = deduped

        python_versions = self._parse_python_preference()

        # SPEC: migrate-pep508-validation::pre-filter — reject obviously
        # malformed dependency lines BEFORE pyproject.toml is written, so a
        # bad requirements.txt produces a one-line error instead of a long
        # uv/setuptools traceback at lock time.
        for dep in dependencies:
            if not _is_likely_valid_pep508_dep(dep):
                log.error(
                    "migrate-dep-invalid: file=%s dep=%s",
                    self.requirements_path,
                    dep,
                )
                print(
                    f"Error: {self.requirements_path.name} contains an"
                    f" invalid PEP 508 requirement: {dep!r}",
                    file=sys.stderr,
                )
                sys.exit(EXIT_CODE_USAGE)

        return RequirementsTxtInfo(
            dependencies, editable_specs, python_versions, indexes, skipped
        )

    def _parse_python_preference(self) -> list[str]:
        """Parse python preference from requirements.txt content."""
        content = self.requirements_path.read_text()
        for line in content.splitlines():
            if line.startswith("# appenv-python-preference: "):
                raw = line.split(":")[1]
                preferences = [x.strip() for x in raw.split(",") if x.strip()]
                if preferences:
                    return preferences
        return ["3.10", "3.11", "3.12", "3.13", "3.14"]

    def _generate_content_with_project(
        self,
        project_name: str,
        description: str,
        dependencies: list[str],
        requires_python: str,
        indexes: list[IndexEntry] | None = None,
    ) -> str:
        """Generate pyproject.toml content string with [project] section."""
        # Generate [project] section
        if dependencies:
            deps_toml = ",\n    ".join(f'"{dep}"' for dep in dependencies)
            deps_block = f"[\n    {deps_toml},\n]"
        else:
            deps_block = "[]"

        project_section = f"""[project]
name = "{project_name}"
version = "0.1.0"
description = "{description}"
dependencies = {deps_block}
requires-python = "{requires_python}"
"""

        # Merge with existing content or create new
        if self.content:
            pyproject_content = self.content.rstrip() + "\n\n" + project_section
        else:
            pyproject_content = project_section

        if indexes:
            pyproject_content = (
                pyproject_content.rstrip() + "\n\n" + self._uv_index_section(indexes)
            )

        return pyproject_content

    @staticmethod
    def _uv_index_section(indexes: list[IndexEntry]) -> str:
        """Render ``[[tool.uv.index]]`` entries from migrated index options."""
        blocks = [
            f'[[tool.uv.index]]\nname = "{index.name}"\nurl = "{index.url}"'
            for index in indexes
        ]
        return "\n\n".join(blocks) + "\n"

    def with_project_section(
        self,
        project_name: str,
        description: str,
        dependencies: list[str],
        requires_python: str = ">=3.10",
    ) -> Pyproject:
        """Add [project] section, write file, return fresh instance.

        This method writes the updated content to disk and returns a new
        Pyproject instance (immutable pattern - cached content stays valid).
        """
        content = self._generate_content_with_project(
            project_name=project_name,
            description=description,
            dependencies=dependencies,
            requires_python=requires_python,
        )
        self.path.write_text(content)
        return Pyproject(self.path.parent)


def create_pyproject(
    target: Path,
    project_name: str,
    description: str,
    dependencies: list[str],
    python_version: str,
) -> Pyproject:
    """Factory function to create a new pyproject.toml file."""
    log.debug(
        "create-pyproject: target=%s name=%s python=%s deps=%s",
        target,
        project_name,
        python_version,
        dependencies,
    )
    pyproject = Pyproject(target)
    return pyproject.with_project_section(
        project_name=project_name,
        description=description,
        dependencies=dependencies,
        requires_python=f">={python_version}",
    )


class LockFile:
    """Encapsulates lockfile operations and diff logic."""

    def __init__(self, base: Path) -> None:
        self.path = base / "uv.lock"

    @property
    def exists(self) -> bool:
        return self.path.exists()

    @cached_property
    def content(self) -> str:
        return self.path.read_text() if self.path.exists() else ""

    def diff(self, uv_bin: UvBin, base: Path, *, verbose: bool) -> str:
        """Run uv lock in temp dir, return diff string."""
        log.debug("lockfile-diff-starting: path=%s", self.path)
        old_content = self.content

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_pyproject = Path(tmpdir) / "pyproject.toml"
            tmp_lock = Path(tmpdir) / "uv.lock"
            shutil.copy(base / "pyproject.toml", tmp_pyproject)
            uv_bin.cmd(["lock"], verbose=verbose, cwd=tmpdir)
            # SPEC: fix-smells-extras-dedup-empty-empty-diff-silent::smell-5 —
            # fail loudly instead of silently rendering the old lockfile as
            # removed. uv exiting 0 without writing uv.lock is a uv bug or a
            # silent network failure (CODEX Art. 5: "Fail loudly").
            if not tmp_lock.exists():
                log.error("uv-lock-no-output: reason=no-lockfile-written")
                msg = "uv lock exited successfully but did not write uv.lock"
                raise CommandError(msg, returncode=1)
            new_content = tmp_lock.read_text()

        has_changes = print_colored_diff(
            old_content, new_content, "uv.lock", "uv.lock (new)"
        )
        if not has_changes:
            return "No changes"
        return "Changed"

    def diff_summary(self, old_lines: set[str]) -> str:
        """Create summary like '✓ Created (+42 lines)'."""
        new_lines = self.read_lockfile_lines()
        # SPEC: fix-smells-extras-dedup-empty-empty-diff-silent::smell-4 —
        # empty→empty is "No changes", not "Created (+0 lines)".
        if not old_lines and not new_lines:
            return "No changes"
        added = new_lines - old_lines
        removed = old_lines - new_lines
        n_added = len(added)
        n_removed = len(removed)

        green = "\033[32m"
        red = "\033[31m"
        reset = "\033[0m"
        check = green + "✓" + reset

        is_new = len(old_lines) == 0
        if n_added == 0 and n_removed == 0 and not is_new:
            return "No changes"
        added_str = f"{green}+{n_added}{reset}"
        removed_str = f"{red}-{n_removed}{reset}"
        if is_new:
            return f"{check} Created ({added_str} lines)"
        return f"{check} Updated ({added_str} / {removed_str} lines)"

    def read_lockfile_lines(self) -> set[str]:
        """Read lockfile lines as a set of non-comment lines."""
        try:
            return {
                stripped
                for line in self.path.read_text().splitlines()
                if (stripped := line.strip()) and not stripped.startswith("#")
            }
        except FileNotFoundError:
            return set()


@dataclass(order=True, frozen=True)
class UvVersion:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        if self.major == 0 and self.minor == 0 and self.patch == 0:
            return "unknown"
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def valid(self) -> bool:
        return self >= UvVersion.minimum()

    @staticmethod
    def unknown() -> UvVersion:
        return UvVersion(0, 0, 0)

    @staticmethod
    def minimum() -> UvVersion:
        return UvVersion(0, 5, 0)

    @staticmethod
    def from_string(version_str: str) -> UvVersion:
        parts = version_str.split(".")
        if len(parts) == VERSION_PARTS_COUNT:
            try:
                major, minor, patch = map(int, parts)
                return UvVersion(major, minor, patch)
            except ValueError:
                log.debug("version-parse-failed: input=%s", version_str)

        msg = f"Invalid version string: {version_str}"
        raise NoValidUvError(msg)


class UvBin:
    """Encapsulates UV binary discovery, version check, and command execution."""

    def __init__(self, appenv_dir: Path) -> None:
        self.appenv_dir = appenv_dir
        self.uv_dir = appenv_dir / ".uv"
        self.managed_uv = self.uv_dir / "bin/uv"
        self.bin = self._get_uv_bin()

    def cmd(self, args: list[str], *, verbose: bool = False, **kwargs: Any) -> str:
        """Execute uv command and return stdout."""
        cmd_args = [str(self.bin)]
        if verbose:
            cmd_args.append("-v")
        cmd_args.extend(str(arg) for arg in args)

        log.debug("uv-cmd-started: args=%s", " ".join(cmd_args))
        uv_output = cmd(cmd_args, **kwargs).decode("utf-8", "replace")
        log.debug("uv-cmd-output: output=%s", uv_output)

        return uv_output

    @cached_property
    def version(self) -> UvVersion:
        return UvBin.get_uv_version(self.bin)

    @staticmethod
    def get_uv_version(uv_path: Path) -> UvVersion:
        """Get uv version by calling uv --version."""
        try:
            result = subprocess.run(
                [uv_path, "--version"],
                capture_output=True,
                text=True,
                check=True,
                env=_build_env(),
            )
        except subprocess.CalledProcessError as e:
            log.debug("uv-version-check-failed: stderr=%s", e.stderr)
            return UvVersion.unknown()

        version_cmd_output = result.stdout.strip()
        log.debug("uv-version-raw: output=%s", version_cmd_output)

        try:
            uv_version_str = version_cmd_output.split()[1]
        except IndexError:
            log.exception("uv-version-parse-failed: output=%s", version_cmd_output)
            return UvVersion.unknown()

        try:
            return UvVersion.from_string(uv_version_str)
        except NoValidUvError:
            log.exception("uv-version-string-invalid: version_str=%s", uv_version_str)
            return UvVersion.unknown()

    def _get_uv_bin(self) -> Path:
        """Get path to valid uv binary via discovery chain:
        1. uv from PATH
        2. Check .appenv/.uv from previous run
        3. Build with nix-build from nixpkgs channel
        4. Build with nix build from nixpkgs flake
        5. pip install
        6. astral.sh installer (curl)
        """
        log.debug("uv-discovery-start: appenv_dir=%s", self.appenv_dir)

        uv_bin = (
            self._try_uv_from_path()
            or self._try_uv_from_appenv_dir()
            or self._try_uv_from_nix_channel()
            or self._try_uv_from_nix_flake()
            or self._try_uv_from_pip()
            or self._try_uv_from_installer()
        )
        if not uv_bin:
            msg = "uv missing and could not be installed. Install it from https://docs.astral.sh/uv/"
            raise NoValidUvError(msg)

        return uv_bin

    def _try_uv_from_path(self) -> Path | None:
        """Try to find uv in PATH."""
        uv_in_path = shutil.which("uv")
        log.debug("uv-path-probe: found=%s", uv_in_path)
        if uv_in_path:
            uv_bin = Path(uv_in_path)
            version = UvBin.get_uv_version(uv_bin)
            log.debug(
                "uv-version-check: version=%s valid=%s source=path",
                version,
                version.valid,
            )

            if version.valid:
                self._cleanup_appenv_uv()
                return uv_bin

        return None

    def _try_uv_from_appenv_dir(self) -> Path | None:
        log.debug("uv-appenv-probe: path=%s", self.managed_uv)
        if not self.managed_uv.exists():
            log.debug("uv-appenv-missing: path=%s", self.managed_uv)
            return None

        version = UvBin.get_uv_version(self.managed_uv)
        log.debug(
            "uv-version-check: version=%s valid=%s source=appenv",
            version,
            version.valid,
        )

        return self.managed_uv if version.valid else None

    def _try_uv_from_nix_channel(self) -> Path | None:
        """Try nix-build with nixpkgs channel"""
        nix_bin = shutil.which("nix")
        log.debug(
            "uv-nix-channel-probe: appenv_dir=%s nix_bin=%s", self.appenv_dir, nix_bin
        )

        if nix_bin is None:
            log.debug(
                "uv-nix-channel-skip: appenv_dir=%s nix_in_path=%s",
                self.appenv_dir,
                nix_bin is not None,
            )
            return None

        action = "Updating" if self.managed_uv.exists() else "Creating"
        log.debug("uv-nix-channel-build: action=%s nix_bin=%s", action, nix_bin)

        try:
            result = subprocess.run(
                ["nix-build", "<nixpkgs>", "-A", "uv", "-o", str(self.uv_dir)],
                capture_output=True,
                text=True,
                check=True,
                env=_build_env(),
            )
        except subprocess.CalledProcessError as e:
            log.debug("uv-nix-channel-failed: stderr=%s", e.stderr)
            return None

        log.debug("uv-nix-channel-succeeded: output=%s", result.stdout)

        version = UvBin.get_uv_version(self.managed_uv)
        log.debug(
            "uv-version-check: version=%s valid=%s source=nix-channel",
            version,
            version.valid,
        )

        return self.managed_uv if version.valid else None

    def _try_uv_from_nix_flake(self) -> Path | None:
        """Tries more expensive but fresh nix build from nixpkgs flake"""

        if shutil.which("nix") is None:
            log.debug("uv-nix-flake-skip: reason=nix-not-in-path")
            return None

        try:
            result = subprocess.run(
                ["nix", "build", "nixpkgs#uv", "--out-link", str(self.uv_dir)],
                capture_output=True,
                check=True,
                text=True,
                env=_build_env(),
            )
        except subprocess.CalledProcessError as e:
            log.debug("uv-nix-flake-failed: stderr=%s", e.stderr)
            return None

        log.debug("uv-nix-flake-succeeded: output=%s", result.stdout)

        version = UvBin.get_uv_version(self.managed_uv)
        log.debug(
            "uv-version-check: version=%s valid=%s source=nix-flake",
            version,
            version.valid,
        )

        return self.managed_uv if version.valid else None

    def _try_uv_from_pip(self) -> Path | None:
        """Try to install uv via pip."""
        log.debug("uv-pip-install-attempt: target=%s", self.uv_dir)

        pip_cmd = self._resolve_pip_command()
        if not pip_cmd:
            log.debug("uv-pip-install-skip: reason=no-pip-found")
            return None

        try:
            result = subprocess.run(
                [*pip_cmd, "install", "uv", "--upgrade", "-t", self.uv_dir],
                capture_output=True,
                text=True,
                check=True,
                env=_build_env(),
            )
        except subprocess.CalledProcessError as e:
            log.debug("uv-pip-install-failed: stderr=%s", e.stderr)
            return None

        log.debug("uv-pip-install-succeeded: output=%s", result.stdout)

        version = UvBin.get_uv_version(self.managed_uv)
        log.debug(
            "uv-version-check: version=%s valid=%s source=pip", version, version.valid
        )

        return self.managed_uv if version.valid else None

    def _try_uv_from_installer(self) -> Path | None:
        """Download uv binary directly from GitHub releases.

        Detects platform, downloads the appropriate tarball via urllib
        (stdlib), extracts and places the binary in .appenv/.uv/bin/uv.
        No curl, no wget, no shell script needed.
        """
        log.debug("uv-download-attempt: starting")

        triple = self._uv_platform_triple()
        if not triple:
            log.debug("uv-download-skip: reason=unsupported-platform")
            return None

        url = f"https://github.com/astral-sh/uv/releases/latest/download/uv-{triple}.tar.gz"

        try:
            import tarfile
            import urllib.error
            import urllib.request

            log.debug("uv-download-start: url=%s", url)
            resp = urllib.request.urlopen(url, timeout=60)
            data = resp.read()

            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                # tar contains uv-<triple>/uv — extract the binary
                for member in tar:
                    if member.name.endswith("/uv") and not member.isdir():
                        member.name = "bin/uv"
                        self.uv_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            tar.extract(member, self.uv_dir, filter="data")
                        except TypeError:
                            # filter= not available before Python 3.12
                            tar.extract(member, self.uv_dir)
                        break
        except (urllib.error.URLError, OSError, tarfile.TarError) as e:
            log.debug("uv-download-failed: error=%s", e)
            return None

        if not self.managed_uv.exists():
            log.debug("uv-download-missing-binary: path=%s", self.managed_uv)
            return None

        version = UvBin.get_uv_version(self.managed_uv)
        log.debug(
            "uv-version-check: version=%s valid=%s source=download",
            version,
            version.valid,
        )

        return self.managed_uv if version.valid else None

    @staticmethod
    def _uv_platform_triple() -> str | None:
        """Return the UV release triple for the current platform.

        Maps Python's platform.machine() and sys.platform to the
        archive naming used by astral-sh/uv GitHub releases.
        Returns None for unsupported platforms.
        """
        import platform

        machine = platform.machine().lower()
        system = sys.platform

        # Map architecture names to UV triples
        if machine in ("x86_64", "amd64"):
            arch = "x86_64"
        elif machine in ("aarch64", "arm64"):
            arch = "aarch64"
        elif machine == "armv7l":
            arch = "armv7"
        else:
            return None

        if system == "linux":
            libc = "musl" if Path("/etc/alpine-release").exists() else "gnu"
            return f"{arch}-unknown-linux-{libc}"
        if system == "darwin":
            return f"{arch}-apple-darwin"
        return None

    def _resolve_pip_command(self) -> list[str] | None:
        """Find a working pip command.

        Tries ensurepip first (blessed way), then falls back to
        shutil.which("pip"/"pip3") for systems where ensurepip is
        disabled (e.g. Debian Bookworm).
        """
        try:
            subprocess.run(
                [sys.executable, "-m", "ensurepip"],
                check=True,
                capture_output=True,
                text=True,
                env=_build_env(),
            )
        except subprocess.CalledProcessError as e:
            log.debug("ensurepip-failed: stderr=%s", e.stderr)
        else:
            log.debug("ensurepip-succeeded: pip_command=python -m pip")
            return [sys.executable, "-m", "pip"]

        # ensurepip failed — try finding pip in PATH
        for candidate in ("pip", "pip3"):
            pip_path = shutil.which(candidate)
            if pip_path:
                log.debug("pip-found: candidate=%s path=%s", candidate, pip_path)
                return [pip_path]

        return None

    def _cleanup_appenv_uv(self) -> None:
        """Remove leftover .appenv/.uv directory."""
        if self.uv_dir.exists():
            remove_path(self.uv_dir)


class NoValidUvError(RuntimeError):
    """Raised when no valid uv binary can be found or installed."""


class CommandError(Exception):
    """Raised when a command (subprocess) fails."""

    def __init__(self, message: str, returncode: int) -> None:
        super().__init__(message)
        self.returncode = returncode


@dataclass(frozen=True)
class AppEnvSettings:
    verbose: bool
    extras: list[str]
    basedir: Path


@dataclass(frozen=True)
class InitParams:
    command_name: str
    dependencies: list[str]
    project_name: str
    description: str
    python_version: str


class AppEnv:
    def __init__(self, original_cwd: Path, settings: AppEnvSettings) -> None:
        self.base = settings.basedir.resolve()
        self.original_cwd = original_cwd
        self.settings = settings

        self.appenv_dir = self.base / ".appenv"
        self.appenv_script = self.base / "appenv"
        self.log_dir = self.appenv_dir / "logs"
        self.venv_real = self.appenv_dir / "venv"
        self.venv_link = self.base / ".venv"
        self.venv_python = self.venv_real / "bin" / "python"

    def _build_env(self, overlays: dict[str, str] | None = None) -> dict[str, str]:
        """Build env dict for child processes.

        Delegates to the module-level :func:`_build_env`.  Every subprocess
        or ``os.execve`` boundary receives the result so the env dict is
        explicit rather than inherited from ``os.environ``.
        """
        return _build_env(overlays)

    def run(self, command: str, argv: list[str]) -> None:
        log_dir = self._set_up_logdir()
        setup_logging(command, log_dir, verbose=self.settings.verbose)

        venv_path = self._prepare_venv(dev_mode=False)
        cmd_path = venv_path / "bin" / command

        if not cmd_path.exists():
            available = sorted(
                p.name
                for p in (venv_path / "bin").iterdir()
                if p.is_file() and not p.name.startswith("_")
            )
            log.error(
                "binary-not-found: command=%s venv=%s available=%s",
                command,
                venv_path / "bin",
                available,
            )
            print(f"Error: Binary '{command}' not found in {venv_path}/bin/")
            print()
            print(f"The symlink '{command}' determines which binary gets executed.")
            print()
            if available:
                print("Available binaries:")
                for name in available:
                    print(f"  {name}")
            else:
                print("No binaries found in the virtual environment.")
            print()
            print("Either:")
            print(f"  - Install a package that provides the '{command}' binary")
            print(f'  - Add a [project.scripts] entry: {command} = "pkg.module:main"')
            print("  - Or create a symlink with the name of an installed binary")
            sys.exit(EXIT_CODE_NOINPUT)

        argv = [str(cmd_path), *argv]
        log.debug("run-chdir: target=%s", self.original_cwd)
        os.chdir(self.original_cwd)

        run_env = self._build_env({"APPENV_BASEDIR": str(self.base)})
        log.info("exec-command: binary=%s argv=%s", cmd_path, argv)
        os.execve(str(cmd_path), argv, run_env)

    def meta(
        self, remaining_args: list[str] | None = None, prog: str = "appenv"
    ) -> None:
        log_dir = self._set_up_logdir()
        setup_logging(prog, log_dir, verbose=self.settings.verbose)

        # Parse the appenv arguments
        parser = UsageArgumentParser(
            prog=prog,
            usage="%(prog)s <COMMAND>",
            description=(
                f"appenv {__version__}\n"
                "\n"
                "appenv pins Python packages to exact versions and\n"
                "exposes their binaries via symlinks — one file, no\n"
                "installation step. It lives as a single script in\n"
                "your project. 'init' creates it there — afterwards\n"
                "use ./appenv or generated symlinks directly."
            ),
            formatter_class=GroupedHelpFormatter,
        )
        parser.add_argument(
            "--version",
            action="version",
            version=f"appenv {__version__}",
        )
        subparsers = parser.add_subparsers(title="Commands")
        p = subparsers.add_parser(
            "update-lockfile", help="Re-resolve dependencies and write uv.lock."
        )
        p.add_argument(
            "--diff",
            action="store_true",
            help="Show what would change without writing the lockfile.",
        )
        p.set_defaults(func=self.update_lockfile)

        p = subparsers.add_parser(
            "init",
            help=("Create project — interactive, or --binary/--dep."),
        )
        p.add_argument(
            "path",
            nargs="?",
            default=None,
            help="Target directory for the new project (default: current directory).",
        )
        p.add_argument(
            "--name",
            help="Project name (default: directory name).",
        )
        p.add_argument(
            "--binary",
            help="Binary to expose as ./<name> symlink (default: 'app').",
        )
        p.add_argument(
            "--dep",
            action="append",
            dest="deps",
            help=(
                "Package dependency. Repeat for multiple:"
                " --dep httpie --dep pytest."
                " Default: same as --binary."
            ),
        )
        p.add_argument(
            "--python-version",
            type=_validate_python_version,
            default=None,
            help="Minimum Python version, e.g. 3.13 (default: 3.13).",
        )
        p.add_argument(
            "--description",
            default=None,
            help="Project description written to pyproject.toml (default: empty).",
        )
        p.set_defaults(func=self.init)

        p = subparsers.add_parser(
            "migrate", help="Convert requirements.txt to pyproject.toml."
        )
        p.add_argument(
            "path",
            nargs="?",
            default=None,
            help="Target directory (default: current directory).",
        )
        p.set_defaults(func=self.migrate)

        p = subparsers.add_parser(
            "self-update", help="Replace the local script with the latest version."
        )
        p.add_argument(
            "--check",
            action="store_true",
            help="Exit 1 if the script is outdated, 0 if current.",
        )
        p.add_argument(
            "path",
            nargs="?",
            default=None,
            help=(
                "Target directory containing the appenv script"
                " (default: project directory)."
            ),
        )
        p.set_defaults(func=self.self_update)

        p = subparsers.add_parser(
            "reset", help="Delete the venv — next run rebuilds from scratch."
        )
        p.set_defaults(func=self.reset)

        p = subparsers.add_parser("version", help="Show appenv version.")
        p.set_defaults(func=self.show_version)

        p = subparsers.add_parser(
            "prepare", help="Create the virtual environment with pinned versions."
        )
        p.set_defaults(func=self.prepare)

        # SPEC: fix-help-passthrough::disable-auto-help-on-passthrough-subparsers
        # — these subparsers only delegate to a wrapped tool (python / uv run /
        # uv), so their own -h/--help is empty noise that swallows the user's
        # intent. add_help=False lets --help fall through parse_known_args into
        # `remaining` and reach the wrapped tool.
        # SPEC: fix-contract-treue::passthrough-tag — _passthrough=True marks
        # these subparsers so unrecognized flags are forwarded to the wrapped
        # tool instead of being rejected by the post-parse strictness check
        # below (non-passthrough subcommands exit 64 on unknown flags).
        p = subparsers.add_parser(
            "python",
            help="Run Python in the project venv.",
            add_help=False,
        )
        p.set_defaults(func=self.python, _passthrough=True)

        p = subparsers.add_parser(
            "run",
            help="Run a command in the project venv (delegates to uv run).",
            add_help=False,
        )
        p.set_defaults(func=self.run_script, _passthrough=True)

        p = subparsers.add_parser(
            "uv",
            help="Run any uv command with project paths set.",
            add_help=False,
        )
        p.set_defaults(func=self.run_uv, _passthrough=True)

        args, remaining = parser.parse_known_args(remaining_args)

        log.debug("parsed-args: args=%s", args)
        log.debug("parsed-args-remaining: args=%s", remaining)

        if not hasattr(args, "func"):
            if remaining:
                log.error("unrecognized-arguments: args=%s", " ".join(remaining))
                print(f"Error: unrecognized arguments: {' '.join(remaining)}")
                parser.print_help()
                sys.exit(EXIT_CODE_USAGE)
            parser.print_help()
            sys.exit(0)

        # SPEC: fix-contract-treue::post-parse-strictness — a matched
        # non-passthrough subcommand with leftover arguments is a usage error
        # (exit 64 via UsageArgumentParser.error). Passthrough subcommands
        # (run/uv/python) forward everything to the wrapped tool unchanged.
        if remaining and not getattr(args, "_passthrough", False):
            parser.error(f"unrecognized arguments: {' '.join(remaining)}")

        args.func(args, remaining)

    def prepare(
        self, args: Namespace | None = None, remaining: list[str] | None = None
    ) -> Path:
        """Prepare venv with production dependencies only."""
        venv_path = self._prepare_venv(dev_mode=False)
        log.debug("prepare-completed: venv=%s", venv_path)
        return venv_path

    def _chdir_to_project(self, target: Path) -> None:
        """Change to target directory and update all derived paths."""
        log.debug("chdir-to-project: target=%s", target)
        os.chdir(target)
        self.base = target.resolve()
        self.appenv_dir = self.base / ".appenv"
        self.appenv_script = self.base / "appenv"
        self.log_dir = self.appenv_dir / "logs"
        self.venv_real = self.appenv_dir / "venv"
        self.venv_link = self.base / ".venv"
        self.venv_python = self.venv_real / "bin" / "python"

    def _check_existing_project(self, pyproject: Pyproject) -> None:
        """Refuse ``init`` when pyproject.toml already has a [project] section.

        Re-init used to rewrite the whole [project] section, silently dropping
        fields appenv cannot round-trip without a TOML writer (version, readme,
        license, classifiers, urls, dynamic, scripts, gui-scripts,
        [project.scripts], [project.optional-dependencies]). Refusing is the
        only safe option under the zero-deps/single-file constraint.
        """
        if not (pyproject.exists and pyproject.has_project_section):
            return
        log.error("init-refused: path=%s reason=project-section-exists", pyproject.path)
        print(f"{pyproject.path} already has a [project] section.")
        print(
            "appenv `init` no longer updates existing projects"
            " (silent field loss risk)."
        )
        print(
            "Use `./appenv uv add` to manage dependencies,"
            " or edit pyproject.toml directly."
        )
        sys.exit(EXIT_CODE_DATAERR)

    def _validate_init_params(self, params: InitParams) -> InitParams:
        """Reject dangerous/invalid init inputs before any file is written.

        SPEC: fix-init-safety-layer::validate-init-params

        Runs after params are resolved and before :func:`create_pyproject`
        and :meth:`_set_up_command_symlink` touch the filesystem, so every
        rejection path exits cleanly with no side effects.

        ``command_name`` must be a non-empty bare name (no path separators,
        no whitespace, not ``.`` or ``..``) — whitespace-bearing names can
        never exist in ``venv/bin/`` (binaries are single path components),
        and an empty name collapses ``self.base / name`` to the project dir
        itself. Any existing entry at ``self.base / command_name`` must
        either be absent, a broken symlink, or an appenv symlink whose
        readlink target is ``"appenv"``. Regular files, directories, and
        foreign symlinks are refused to prevent silent data loss.

        Empty or whitespace-only dependencies are rejected before they reach
        ``pyproject.toml`` (where they would only surface as a confusing
        ``uv lock`` parse error); the rest is deduplicated via
        :func:`_dedup_preserve_order`. Returns a validated copy
        (``InitParams`` is frozen).
        """
        name = params.command_name
        if not name:
            log.error("init-binary-empty: name=%s", name)
            print("Error: --binary must not be empty.", file=sys.stderr)
            sys.exit(EXIT_CODE_USAGE)

        if (
            "/" in name
            or "\\" in name
            or name in {".", ".."}
            or any(c.isspace() for c in name)
        ):
            log.error("init-binary-invalid: name=%s", name)
            print(
                f"Error: --binary must be a bare name (no path, no whitespace),"
                f" got {name!r}.",
                file=sys.stderr,
            )
            sys.exit(EXIT_CODE_USAGE)

        link = self.base / name
        # ``link.exists()`` is False for broken symlinks, so they fall through
        # to the safe path — matches the historical broken-symlink refresh
        # behavior in :meth:`_set_up_command_symlink`. Only a working symlink
        # whose target is our own ``"appenv"`` is refresh-safe.
        if link.exists() and (not link.is_symlink() or os.readlink(link) != "appenv"):
            log.error("init-binary-conflict: path=%s", link)
            print(
                f"Error: {link} exists and is not an appenv symlink"
                " — refusing to overwrite.",
                file=sys.stderr,
            )
            sys.exit(EXIT_CODE_USAGE)

        if any(not d.strip() for d in params.dependencies):
            log.error("init-dep-empty: deps=%s", params.dependencies)
            print(
                "Error: --dep must not be empty or whitespace-only.",
                file=sys.stderr,
            )
            sys.exit(EXIT_CODE_USAGE)

        return replace(params, dependencies=_dedup_preserve_order(params.dependencies))

    def _resolve_init_params_noninteractive(
        self, args: Namespace, target: Path
    ) -> InitParams:
        """Resolve init params when all required flags are provided."""
        return InitParams(
            command_name=args.binary,
            dependencies=args.deps,
            project_name=args.name or target.name,
            description=args.description or "",
            python_version=args.python_version or "3.13",
        )

    def _resolve_init_params_interactive_new(
        self, pyproject: Pyproject, target: Path
    ) -> InitParams:
        """Interactive wizard for creating a brand-new project."""
        if pyproject.exists:
            print(f"Adding [project] section to existing {pyproject.path}\n")
        else:
            print(f"Let's create a new appenv project in {self.base}")
            print("I'll ask a few questions, then create pyproject.toml here\n")

        print("\nEnter dependencies (one per line, empty line to finish):")
        print("  Default: app")
        dependencies = []
        while True:
            dep = input("  Dependency: ").strip()
            if not dep:
                break
            dependencies.append(dep)
        if not dependencies:
            dependencies = ["app"]

        command_name = input(
            "\nBinary to expose (creates ./<name> symlink) [app] "
        ).strip()
        if not command_name:
            command_name = "app"

        project_name = input(f"\nProject name [{target.name}]: ").strip()
        if not project_name:
            project_name = target.name

        description = input("Description []: ").strip()

        python_version = input("Minimum Python version [3.13]: ").strip()
        if not python_version:
            python_version = "3.13"

        return InitParams(
            command_name=command_name,
            dependencies=dependencies,
            project_name=project_name,
            description=description,
            python_version=python_version,
        )

    def init(
        self, args: Namespace | None = None, remaining: list[str] | None = None
    ) -> None:
        """Create a new pyproject.toml project."""
        target = self._resolve_init_target(args)
        self._chdir_to_project(target)
        pyproject = Pyproject(self.base)
        self._check_existing_project(pyproject)

        params = self._resolve_init_params_with_eof_guard(args, pyproject, target)
        params = self._validate_init_params(params)
        self._ensure_appenv_script()

        self._atomic_write_and_lock(params, pyproject)

        ensure_gitignore(self.base, _GITIGNORE_ENTRIES)
        log.info(
            "init-completed: project=%s command=%s",
            params.project_name,
            params.command_name,
        )
        print("\n=== Appenv project initialized ===")
        command_link = self.base / params.command_name
        display_path = os.path.relpath(command_link, self.original_cwd)
        if "/" not in display_path:
            display_path = f"./{display_path}"
        print(f"\nUse `{display_path}` to run the {params.command_name} binary")

    def _resolve_init_target(self, args: Namespace | None) -> Path:
        """Resolve the project directory for ``init``.

        With ``args.path`` set, create and resolve that subdirectory under the
        original CWD; otherwise target the original CWD itself.
        """
        if args and args.path:
            target = (self.original_cwd / args.path).resolve()
            target.mkdir(parents=True, exist_ok=True)
        else:
            target = self.original_cwd.resolve()
        return target

    def _resolve_init_params_with_eof_guard(
        self, args: Namespace | None, pyproject: Pyproject, target: Path
    ) -> InitParams:
        """Resolve init params, surfacing stdin EOF as a clean USAGE exit.

        SPEC: fix-contract-treue::eof-clean-exit — stdin EOF during the
        interactive wizard must surface as a clean USAGE exit with a usage
        hint, not a raw traceback. The wrap sits at the params-resolution
        stage so it does not collide with the rollback wrap around the
        write+lock stage (see fix-rollback-on-failure).
        """
        try:
            if args and getattr(args, "binary", None) is not None:
                if getattr(args, "deps", None) is None:
                    log.error(
                        "init-missing-dep: binary=%s", getattr(args, "binary", None)
                    )
                    print(
                        "Error: --dep is required when creating a new project.",
                        file=sys.stderr,
                    )
                    print(
                        "Example: appenv init --binary http --dep httpie",
                        file=sys.stderr,
                    )
                    sys.exit(EXIT_CODE_USAGE)
                params = self._resolve_init_params_noninteractive(args, target)
            elif args and getattr(args, "deps", None) is not None:
                log.error("init-binary-required: deps=%s", getattr(args, "deps", None))
                print(
                    "Error: --binary is required when --dep is provided.",
                    file=sys.stderr,
                )
                print(
                    "Example: appenv init --binary http --dep httpie",
                    file=sys.stderr,
                )
                sys.exit(EXIT_CODE_USAGE)
            elif not sys.stdin.isatty():
                log.error("init-requires-tty: stdin_isatty=False")
                print(
                    "Error: 'init' is interactive and needs a TTY.",
                    file=sys.stderr,
                )
                print(file=sys.stderr)
                print(
                    "Provide all required flags for non-interactive use:",
                    file=sys.stderr,
                )
                print(
                    "  appenv init --binary http --dep httpie --dep pytest"
                    " --name myproject",
                    file=sys.stderr,
                )
                print(file=sys.stderr)
                print(
                    "Required: --binary, --dep (at least one)."
                    " Optional: --name, --python-version, --description.",
                    file=sys.stderr,
                )
                sys.exit(EXIT_CODE_USAGE)
            else:
                params = self._resolve_init_params_interactive_new(pyproject, target)
        except EOFError:
            log.exception("init-interactive-eof: stage=params-resolution")
            print(
                "\nError: end of input — interactive init needs answers.",
                file=sys.stderr,
            )
            print(
                "Use: appenv init --binary NAME --dep PACKAGE --name PROJECT",
                file=sys.stderr,
            )
            sys.exit(EXIT_CODE_USAGE)
        return params

    def _atomic_write_and_lock(self, params: InitParams, pyproject: Pyproject) -> None:
        """Atomically create pyproject.toml, the command symlink, and the lockfile.

        SPEC: fix-rollback-on-failure::atomic-write-lock — the
        create+symlink+lock sequence must be atomic. Snapshot pyproject
        bytes and command-link state BEFORE any mutation (outside the
        try-block, so a snapshot failure is never swallowed by the
        restore path). The try/except below is a spec-required cleanup
        handler: on any failure during the write+lock stage (uv-lock
        CalledProcessError, OSError, KeyboardInterrupt) it restores
        pyproject to its previous bytes — or deletes it when newly
        created — removes a command symlink this run created, then
        re-raises so the original error and its exit code propagate.
        """
        command_link = self.base / params.command_name
        command_link_existed = command_link.is_symlink() or command_link.exists()
        pyproject_path = pyproject.path
        original_pyproject = (
            pyproject_path.read_text() if pyproject_path.exists() else None
        )

        try:
            pyproject = create_pyproject(
                target=self.base,
                project_name=params.project_name,
                description=params.description,
                dependencies=params.dependencies,
                python_version=params.python_version,
            )
            log.info(
                "created-pyproject: path=%s project=%s python=%s deps=%s",
                pyproject.path,
                params.project_name,
                params.python_version,
                params.dependencies,
            )
            print(f"Created {pyproject.path}")

            self._set_up_command_symlink(
                command_name=params.command_name,
                project_name=params.project_name,
            )

            print("Generating new lock file ...")
            log.info("generating-lockfile: project=%s", params.project_name)
            uv = ensure_uv(self.appenv_dir)
            self._uv_lock(uv, diff=False)
        except BaseException:
            log.exception(
                "init-rollback: command=%s new_pyproject=%s",
                params.command_name,
                original_pyproject is None,
            )
            if original_pyproject is None:
                pyproject_path.unlink(missing_ok=True)
            else:
                pyproject_path.write_text(original_pyproject)
            if not command_link_existed:
                command_link.unlink(missing_ok=True)
            print(
                "Error: initialization failed — pyproject.toml restored"
                " to previous state.",
                file=sys.stderr,
            )
            raise

    def migrate(
        self, args: Namespace | None = None, remaining: list[str] | None = None
    ) -> None:
        """Migrate from requirements.txt to pyproject.toml."""
        if args and args.path:
            target = (self.original_cwd / args.path).resolve()
            target.mkdir(parents=True, exist_ok=True)
        else:
            target = self.original_cwd.resolve()

        self._chdir_to_project(target)

        pyproject = Pyproject(self.base)
        if pyproject.has_project_section:
            log.info(
                "migrate-skipped: path=%s reason=project-section-exists", pyproject.path
            )
            print(
                f"pyproject.toml in {self.base} already has a [project] section"
                " — nothing to migrate.\n\n"
                "`migrate` converts requirements.txt-based projects to pyproject.toml."
            )
            return

        # SPEC: migrate-pep508-validation::order — validate requirements.txt
        # BEFORE announcing the migration. Accessing the cached property
        # triggers _parse_requirements_file (which runs the PEP 508 pre-filter),
        # so a rejection exits here with a one-line error instead of printing
        # the misleading "Migrating..." / "Adding [project] section" banner
        # first and erroring out a moment later.
        if pyproject.requirements_path.exists():
            _ = pyproject.requirements_txt_info

        if pyproject.exists:
            log.info("migrate-adding-section: path=%s", pyproject.path)
            print("Adding [project] section to existing pyproject.toml.\n")
        elif pyproject.can_be_created_from_requirements_txt:
            log.info("migrate-from-requirements: path=%s", pyproject.path)
            print("Migrating from requirements.txt to pyproject.toml...\n")
        else:
            log.warning("migrate-no-source: base=%s", self.base)
            print(f"No requirements.txt found in {self.base}.")
            print("Use 'init' to create a new project.")
            return

        self._ensure_appenv_script(update=True)

        uv = ensure_uv(self.appenv_dir)

        pyproject = pyproject.migrate_from_requirements_txt()
        pyproject.print_migration_info()

        uv_lock_out = self._uv_lock(uv, diff=False)
        print(uv_lock_out)

        # Also cleans up old .appenv hash-based venvs
        print("Preparing/cleaning .appenv directory ...")
        self._prepare_appenv_dir()

        ensure_gitignore(self.base, _GITIGNORE_ENTRIES)
        log.info("migrate-completed: base=%s", self.base)
        print("\n=== Pyproject Migration completed ===")
        print("requirements.{txt,lock} kept as legacy. You can delete these files now.")

    def self_update(
        self, args: Namespace | None = None, remaining: list[str] | None = None
    ) -> None:
        """Update the local ./appenv script to match the running version."""
        log.debug(
            "self-update-started: appenv_script=%s running_version=%s",
            self.appenv_script,
            __version__,
        )

        # Determine target script path
        if args and getattr(args, "path", None) is not None:
            target_script = Path(args.path).resolve() / "appenv"
        elif (
            os.environ.get("APPENV_BASEDIR")
            or self.base != Path(__file__).parent.resolve()
        ):
            target_script = self.appenv_script
        elif self.appenv_script.resolve() == Path(__file__).resolve():
            # Standalone script: running as ./appenv, can only update via PyPI
            self._self_update_via_uvx(args)
            return  # pragma: no cover — unreachable without mocked sys.exit
        else:
            # Externally managed (uvx, pip install, etc.)
            log.error(
                "self-update-externally-managed: script=%s", Path(__file__).resolve()
            )
            print(
                "Error: appenv is running from an externally managed"
                " environment and cannot update itself in place."
            )
            print(
                "HINT: To update the appenv script in your current directory,"
                " use: appenv self-update ."
            )
            sys.exit(EXIT_CODE_USAGE)

        if not target_script.exists():
            log.error("self-update-script-not-found: path=%s", target_script)
            print(f"Error: No appenv script found at {target_script}")
            sys.exit(EXIT_CODE_NOINPUT)

        local_version = self._extract_version(target_script)
        running_version = __version__
        local_label = local_version if local_version else "unknown"

        if local_version == running_version:
            print(f"{target_script} is already up-to-date (version {running_version}).")
            if args and args.check:
                sys.exit(0)
            return

        if args and args.check:
            log.error(
                "version-drift: running=%s local=%s",
                running_version,
                local_label,
            )
            print(
                f"Version drift detected: {target_script} is {local_label}, "
                f"running appenv is {running_version}."
            )
            sys.exit(1)

        # Perform the update
        bootstrap_data = Path(__file__).read_bytes()
        target_script.write_bytes(bootstrap_data)
        target_script.chmod(0o755)
        log.info(
            "self-update-completed: path=%s old_version=%s new_version=%s",
            target_script,
            local_label,
            running_version,
        )
        print(f"Updated {target_script} ({local_label} -> {running_version})")

    def _self_update_via_uvx(self, args: Namespace | None = None) -> None:
        """Update standalone script by delegating to uvx for latest PyPI version."""
        uv = ensure_uv(self.appenv_dir)

        cmd = [
            uv.bin,
            "tool",
            "run",
            "--prerelease=allow",
            "appenv",
            "self-update",
        ]
        if args and getattr(args, "check", False):
            cmd.append("--check")
        cmd.append(str(self.base))

        result = subprocess.run(
            cmd, env=self._build_env({"APPENV_BASEDIR": str(self.base)})
        )
        if result.returncode:
            log.error(
                "self-update-via-uvx-failed: returncode=%d cmd=%s",
                result.returncode,
                cmd,
            )
        sys.exit(result.returncode)

    def python(self, args: Namespace, remaining: list[str]) -> None:
        self.run("python", remaining)

    def run_script(self, args: Namespace, remaining: list[str]) -> None:
        """Run a command in the project venv via uv run."""
        self.run_uv(args, ["run", *remaining])

    def run_uv(self, args: Namespace, remaining: list[str]) -> None:
        """Run uv with the appenv-configured uv binary."""
        # SPEC: fix-contract-treue::run-uv-pre-flight — refuse to exec uv
        # without a pyproject.toml, matching prepare/python/update-lockfile
        # (exit 67 NOINPUT). run_script() delegates here, so it inherits this.
        ensure_pyproject(self.base)
        uv = ensure_uv(self.appenv_dir)

        uv_argv = [str(uv.bin), *remaining]
        log.debug("run-uv-chdir: target=%s", self.base)
        os.chdir(self.base)

        run_env = self._build_env({"UV_PROJECT_ENVIRONMENT": str(self.venv_real)})
        log.info("exec-uv: binary=%s argv=%s", uv.bin, uv_argv)
        os.execve(str(uv.bin), uv_argv, run_env)

    def show_version(
        self, args: Namespace | None = None, remaining: list[str] | None = None
    ) -> None:
        """Show appenv version."""
        print(f"appenv {__version__}")

    def reset(
        self, args: Namespace | None = None, remaining: list[str] | None = None
    ) -> None:
        """Remove appenv-managed files/directories"""
        # Remove symlink if it exists
        log.debug("reset-venv-link: path=%s", self.venv_link)
        if self.venv_link.is_symlink():
            log.info("removing-venv-link: path=%s", self.venv_link)
            print(f"Removing {self.venv_link} symlink ...")
            self.venv_link.unlink()

        # Remove real venv in .appenv
        log.debug("reset-venv-real: path=%s", self.venv_real)
        if self.venv_real.exists():
            log.info("removing-venv: path=%s", self.venv_real)
            print(f"Removing {self.venv_real} ...")
            shutil.rmtree(self.venv_real)

        # Note: .venv may exist as a real directory (not managed by appenv)
        if self.venv_link.exists() and not self.venv_link.is_symlink():
            print(
                f"Note: {self.venv_link} exists but is not a symlink. "
                f"Not removing it automatically."
            )

        # Clean up old hash-based venvs in .appenv (keep logs, profiling)
        if self.appenv_dir.exists():
            for path in list(self.appenv_dir.iterdir()):
                if path.name not in {"venv", ".uv", "logs", "profiling", "current"}:
                    print(f"Removing {path} ...")
                    remove_path(path)

    def update_lockfile(
        self, args: Namespace | None = None, remaining: list[str] | None = None
    ) -> None:
        log.debug(
            "update-lockfile-started: base=%s diff=%s",
            self.base,
            args.diff if args else False,
        )
        ensure_pyproject(self.base)
        uv = ensure_uv(self.appenv_dir)
        os.chdir(self.base)
        uv_lock_out = self._uv_lock(uv, diff=args.diff if args else False)
        print(uv_lock_out)

    def _ensure_appenv_script(self, *, update: bool = False) -> None:
        """
        Creates local ./appenv script if needed.

        When the script already exists and versions differ:
        - update=True: replaces it (used by migrate)
        - update=False: warns only (used by init)
        """
        log.debug("appenv-script-check: path=%s", self.appenv_script)
        if not self.appenv_script.exists():
            log.info("creating-appenv-script: path=%s", self.appenv_script)
            bootstrap_data = Path(__file__).read_bytes()
            self.appenv_script.write_bytes(bootstrap_data)
            self.appenv_script.chmod(0o755)
            print(f"Created {self.appenv_script}")
            return

        local_version = self._extract_version(self.appenv_script)
        running_version = __version__
        log.debug(
            "appenv-script-version-check: local=%s running=%s",
            local_version,
            running_version,
        )
        if local_version == running_version:
            log.debug("appenv-script-version-match: skipping")
            return

        if update:
            local_label = local_version if local_version else "unknown"
            log.info(
                "updating-appenv-script: path=%s old=%s new=%s",
                self.appenv_script,
                local_label,
                running_version,
            )
            bootstrap_data = Path(__file__).read_bytes()
            self.appenv_script.write_bytes(bootstrap_data)
            self.appenv_script.chmod(0o755)
            print(f"Updated {self.appenv_script} ({local_label} -> {running_version})")
        else:
            local_label = local_version if local_version else "unknown"
            log.warning(
                "appenv-version-mismatch: local=%s running=%s path=%s",
                local_label,
                running_version,
                self.appenv_script,
            )
            print(
                f"Warning: {self.appenv_script} is version {local_label}, "
                f"running appenv is {running_version}."
            )
            print("Run './appenv self-update' to update the script.")

    @staticmethod
    def _extract_version(script: Path) -> str | None:
        """Extract __version__ from an appenv script file."""
        content = script.read_text(errors="replace")
        match = re.search(r'__version__ = "([^"]+)"', content)
        return match.group(1) if match else None

    def _uv_lock(self, uv: UvBin, *, diff: bool) -> str:
        lock = LockFile(self.base)

        if diff:
            log.info("lockfile-diff: path=%s", lock.path)
            print("Diff mode: only check lockfile changes ...")
            update_info = lock.diff(uv, self.base, verbose=self.settings.verbose)
        else:
            old_lines = lock.read_lockfile_lines()
            log.info("updating-lockfile: path=%s", lock.path)
            print("Updating lock file ...")
            uv.cmd(["lock"], verbose=self.settings.verbose, cwd=self.base)

            update_info = lock.diff_summary(old_lines)

        return update_info

    def _uv_sync(
        self, *, dev_mode: bool, uv: UvBin, env: dict[str, str] | None = None
    ) -> None:
        # Validate lockfile is consistent with pyproject before frozen sync
        if not dev_mode:
            try:
                uv.cmd(["lock", "--check"], env=env)
            except CommandError:
                log.exception("lockfile-stale: reason=pyproject-changed")
                print(
                    "Lockfile is stale (pyproject.toml changed since last lock)."
                    "\nRun: ./appenv update-lockfile"
                )
                sys.exit(EXIT_CODE_DATAERR)

        # Sync dependencies (idempotent)
        sync_args = ["sync"]

        if not dev_mode:
            sync_args.extend(["--no-dev", "--frozen"])

        if self.settings.extras:
            sync_args.extend(["--extra", ",".join(self.settings.extras)])

        log.debug("uv-sync-extras: extras=%s", self.settings.extras)
        uv.cmd(sync_args, env=env)

    def _set_up_logdir(self) -> Path:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        return self.log_dir

    def _check_venv_health(self) -> None:
        """Check venv for corruption or stale Python version; remove if needed."""
        if self.venv_real.exists() and not self.venv_python.exists():
            log.warning(
                "corrupted-venv: venv=%s bin_python_missing=%s",
                self.venv_real,
                self.venv_python,
            )
            shutil.rmtree(self.venv_real)

        # stale-venv-recreate — check venv Python version against requires-python
        if not (self.venv_real.exists() and self.venv_python.exists()):
            return

        # stale-venv-recreate — handle broken binary or malformed output
        try:
            result = cmd([str(self.venv_python), "--version"], quiet=True)
            venv_version_str = result.decode().strip()
            venv_version = ".".join(venv_version_str.split()[1].split(".")[:2])
        except (CommandError, IndexError, OSError) as e:
            log.warning(
                "venv-health-check-failed: venv=%s python=%s error=%s",
                self.venv_real,
                self.venv_python,
                e,
            )
            print("Recreating venv: Python version could not be determined")
            shutil.rmtree(self.venv_real)
            return

        min_version, max_version = Pyproject(self.base).requires_python
        if min_version and not version_satisfies_constraints(
            venv_version, min_version, max_version
        ):
            constraint = ">=" + min_version
            if max_version:
                constraint += ",<" + max_version
            log.warning(
                "venv-python-stale: venv_python=%s requires_python=%s",
                venv_version,
                constraint,
            )
            print(
                f"Recreating venv: Python {venv_version} does not satisfy"
                f" requires-python {constraint}"
            )
            shutil.rmtree(self.venv_real)

    def _ensure_venv_symlinks(self) -> None:
        """Create/update .venv symlink and legacy current symlink."""
        if self.venv_link.is_symlink():
            self.venv_link.unlink()
        if not self.venv_link.exists():
            self.venv_link.symlink_to(
                os.path.relpath(self.venv_real, self.base), target_is_directory=True
            )
        elif not self.venv_link.is_symlink():
            log.warning(
                "venv-link-conflict: path=%s expected_symlink_to=%s",
                self.venv_link,
                self.venv_real,
            )
            print(
                f"Warning: {self.venv_link} exists but is not a symlink. "
                f"Expected .venv -> {self.venv_real}. "
                f"Remove {self.venv_link} manually if you want appenv to manage it."
            )

        current_link = self.appenv_dir / "current"
        if current_link.is_symlink():
            current_link.unlink()
        if not current_link.exists():
            current_link.symlink_to("venv", target_is_directory=True)

    def _prepare_venv(self, *, dev_mode: bool) -> Path:
        ensure_pyproject(self.base)
        ensure_lock_file(self.base)
        uv = ensure_uv(self.appenv_dir)
        os.chdir(self.base)

        self._prepare_appenv_dir()

        run_env = self._build_env({"UV_PROJECT_ENVIRONMENT": str(self.venv_real)})

        log.debug(
            "prepare-venv-context: base=%s venv=%s python=%s dev_mode=%s",
            self.base,
            self.venv_real,
            Path(sys.executable).resolve(),
            dev_mode,
        )

        self._check_venv_health()

        if not self.venv_real.exists():
            log.info("creating-venv: python=%s path=%s", sys.executable, self.venv_real)
            print("Creating fresh venv with uv ...")
            uv.cmd(
                ["venv", "--python", sys.executable, str(self.venv_real)], env=run_env
            )

        self._uv_sync(dev_mode=dev_mode, uv=uv, env=run_env)

        if self.venv_python.exists():
            log.debug(
                "venv-python: path=%s realpath=%s",
                self.venv_python,
                self.venv_python.resolve(),
            )
            result = cmd([str(self.venv_python), "--version"], quiet=True, env=run_env)
            log.debug("venv-python-version: version=%s", result.decode().strip())

        self._ensure_venv_symlinks()

        return self.venv_real

    def _set_up_command_symlink(self, command_name: str, project_name: str) -> None:
        """Create or refresh the ``./<command_name> -> appenv`` symlink.

        SPEC: fix-init-safety-layer::set-up-command-symlink

        Safety is guaranteed upstream by :meth:`_validate_init_params` when
        this is called from :meth:`init`. Any existing entry (regular file,
        directory, or symlink) is unlinked unconditionally — callers that
        invoke this outside ``init`` are responsible for validating the
        target first.
        """
        command_link = self.base / command_name
        if command_link.is_symlink() or command_link.exists():
            command_link.unlink(missing_ok=True)
        command_link.symlink_to("appenv")
        display_path = os.path.relpath(command_link, self.original_cwd)
        if "/" not in display_path:
            display_path = f"./{display_path}"
        print(f"Created {display_path} -> appenv (runs the {command_name} binary)")

    def _prepare_appenv_dir(self) -> None:
        """Remove old hash-based venvs and files from .appenv directory."""
        self.appenv_dir.mkdir(exist_ok=True)
        keep = {"venv", ".uv", "logs", "profiling", "current"}
        for path in list(self.appenv_dir.iterdir()):
            if path.name not in keep:
                log.debug("appenv-cleanup-entry: name=%s", path.name)
                remove_path(path)

        # Remove dangling current symlink (left over from hash-based venvs)
        current = self.appenv_dir / "current"
        if current.is_symlink() and not current.exists():
            log.debug("appenv-cleanup-dangling-current: removing")
            current.unlink()


def ensure_uv(appenv_dir: Path) -> UvBin:
    """Ensure uv is available and meets minimum version.

    Exits with error if uv is not available or too old.
    Returns UvBin instance.
    """
    uv = UvBin(appenv_dir)
    log.debug("ensure-uv-bin: path=%s", uv.bin)

    version = uv.version
    log.debug("ensure-uv-version: version=%s", version)

    if version is None or not version.valid:
        log.error(
            "uv-version-invalid: bin=%s version=%s minimum=%s",
            uv.bin,
            version,
            UvVersion.minimum(),
        )
        print(f"Error: cannot use uv binary: {uv.bin}. Version is: {version}")
        print(f"Minimum required version: {UvVersion.minimum()}")
        sys.exit(EXIT_CODE_UNAVAILABLE)

    return uv


def ensure_pyproject(base: Path) -> Pyproject:
    """Ensure pyproject.toml exists with [project] section, return Pyproject."""
    pyproject = Pyproject(base)
    if pyproject.has_project_section:
        log.debug("pyproject-has-project-section: path=%s", pyproject.path)
        return pyproject

    if pyproject.exists:
        log.error("pyproject-missing-project-section: path=%s", pyproject.path)
        print(f"Error: {pyproject.path} has no [project] section.")
    else:
        log.error("pyproject-not-found: path=%s", pyproject.path)
        print(
            f"Error: No pyproject.toml found in {base}.\n\n"
            "appenv looks for pyproject.toml next to itself (the appenv script).\n"
            "If you meant a different project, use its local ./appenv script."
        )

    if pyproject.can_be_created_from_requirements_txt:
        print("Legacy requirements.txt found.")
        print("Run: ./appenv migrate")
        sys.exit(EXIT_CODE_DATAERR)
    else:
        print("Run ./appenv init")
        sys.exit(EXIT_CODE_NOINPUT)


def ensure_lock_file(base: Path) -> LockFile:
    """Ensure lockfile exists, return LockFile instance."""
    lock = LockFile(base)
    if not lock.exists:
        log.error("lockfile-not-found: path=%s", lock.path)
        print("No uv.lock found. Run: ./appenv update-lockfile")
        sys.exit(EXIT_CODE_NOINPUT)

    log.debug("lockfile-found: path=%s", lock.path)
    return lock


# SPEC: fix-gitignore-consistency::shared-gitignore-entries
# Single source of truth for the .gitignore entries written by `init` and
# `migrate`. Both commands create the `.appenv/` tree, so both must ignore it.
_GITIGNORE_ENTRIES: list[str] = [".venv", ".appenv", ".batou-lock"]


def ensure_gitignore(base: Path, entries: list[str]) -> None:
    """Ensure .gitignore contains the given entries.

    Idempotent: appends only missing entries, never modifies existing content.
    """
    gitignore_path = base / ".gitignore"

    if gitignore_path.exists():
        existing_lines = gitignore_path.read_text().splitlines()
    else:
        existing_lines = []

    existing_set = {line for line in existing_lines if line.strip()}
    missing = [e for e in entries if e not in existing_set]

    if not missing:
        return

    new_content = "\n".join(existing_lines)
    if new_content and not new_content.endswith("\n"):
        new_content += "\n"
    new_content += "\n".join(missing) + "\n"
    gitignore_path.write_text(new_content)
    if existing_lines:
        log.info("updated-gitignore: path=%s entries=%s", gitignore_path, missing)
        print(f"Updated {gitignore_path}")
    else:
        log.info("created-gitignore: path=%s entries=%s", gitignore_path, missing)
        print(f"Created {gitignore_path}")


def _build_env(overlays: dict[str, str] | None = None) -> dict[str, str]:
    """Build env dict for child processes.

    Starts from ``os.environ.copy()``, drops ``PYTHONPATH``, applies caller
    overlays. Every subprocess boundary must receive the result of this
    function so that the env dict is explicit rather than inherited from
    the parent's ``os.environ``.
    """
    env = os.environ.copy()
    dropped_pythonpath = env.pop("PYTHONPATH", None)
    if dropped_pythonpath is not None:
        log.debug("build-env-dropped-pythonpath: value=%s", dropped_pythonpath)
    if overlays:
        env.update(overlays)
    return env


def cmd(
    c: str | list[str],
    *,
    merge_stderr: bool = True,
    quiet: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> bytes:
    try:
        if isinstance(c, str):
            cmd_list = [c]
            is_shell = True
        else:
            cmd_list = c
            is_shell = False
        stderr = subprocess.STDOUT if merge_stderr else None
        if env is None:
            env = _build_env()
        return subprocess.check_output(
            cmd_list, shell=is_shell, stderr=stderr, cwd=cwd, env=env
        )
    except subprocess.CalledProcessError as e:
        decoded_output = e.output.decode("utf-8", "replace")
        if not quiet:
            log.exception(
                "subprocess-failed: %s exit_code=%d output=%s",
                c,
                e.returncode,
                decoded_output,
            )
            print(f"{c} returned with exit code {e.returncode}")
            print(decoded_output)
        raise CommandError(decoded_output, e.returncode) from e


def ensure_best_python(base: Path) -> None:
    """Ensure best Python for pyproject.toml workflow.

    Reads requires-python from pyproject.toml and selects the newest
    available Python that satisfies the constraint.

    When running inside a virtual environment (sys.prefix != sys.base_prefix),
    skips re-exec only if the current Python already satisfies the constraint.
    This handles both legitimate venvs (uvx appenv init) and NixOS Python
    environments where sys.prefix != sys.base_prefix is always true.
    """
    log.debug(
        "ensure-best-python-started: base=%s current_python=%s", base, sys.executable
    )
    if "APPENV_BEST_PYTHON" in os.environ:
        return

    pyproject = Pyproject(base)
    min_version, max_version = pyproject.requires_python

    log.debug("requires-python-constraints: min=%s max=%s", min_version, max_version)
    if min_version is None:
        min_version = "3.10"

    if sys.prefix != sys.base_prefix:
        current = f"{sys.version_info[0]}.{sys.version_info[1]}"
        if version_satisfies_constraints(current, min_version, max_version):
            log.debug(
                "venv-python-compatible: version=%s action=skip-re-exec",
                current,
            )
            return
        log.debug(
            "venv-python-incompatible: version=%s action=search",
            current,
        )

    available = find_available_pythons()
    log.debug("python-candidates: count=%d candidates=%s", len(available), available)
    current_python = str(Path(sys.executable).resolve())

    for version, path in available:
        if not version_satisfies_constraints(version, min_version, max_version):
            log.debug("python-skip-constraint: version=%s", version)
            continue

        resolved_path = str(Path(path).resolve())
        if resolved_path == current_python:
            # Already running this version
            log.debug("python-already-best: path=%s", resolved_path)
            return

        # Try whether this Python works
        try:
            subprocess.check_call(
                [resolved_path, "-c", "print(1)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_build_env(),
            )
        except subprocess.CalledProcessError:
            log.debug("python-skip-broken: version=%s", version)
            continue

        # Re-exec with this Python
        argv = [Path(path).name, *sys.argv]
        run_env = _build_env({"APPENV_BEST_PYTHON": path})
        log.debug(
            "python-re-exec: path=%s current_python=%s selected_version=%s"
            " min=%s max=%s candidates=%s",
            path,
            current_python,
            version,
            min_version,
            max_version,
            [(v, p) for v, p in available],
        )
        os.execve(path, argv, run_env)

    # No suitable Python found
    log.error(
        "no-compatible-python: min=%s max=%s available=%s",
        min_version,
        max_version,
        [(v, p) for v, p in available],
    )
    if max_version:
        print(f"requires-python: >={min_version},<{max_version}")
    else:
        print(f"requires-python: >={min_version}")
    print("Available versions:")
    for version, path in available:
        print(f"  python{version}: {path}")
    sys.exit(EXIT_CODE_DATAERR)


def find_available_pythons() -> list[tuple[str, str]]:
    """Find all available Python versions in PATH.

    Returns list of (version_str, path) tuples, sorted by version (newest first).
    """
    pythons = [
        (f"3.{i}", path)
        for i in range(10, 25)
        if (path := shutil.which(f"python3.{i}"))
    ]

    # macos-python-fallback — check unversioned python3 (on macOS)
    bare_python = shutil.which("python3")
    if bare_python:
        resolved_existing = {Path(p).resolve() for _, p in pythons}
        if Path(bare_python).resolve() not in resolved_existing:
            try:
                raw = subprocess.check_output(
                    [bare_python, "--version"],
                    stderr=subprocess.STDOUT,
                    env=_build_env(),
                )
                parts = raw.decode().strip().split()
                # "Python 3.12.0" -> "3.12"
                version_str = ".".join(parts[1].split(".")[:2])
                major, minor = (int(x) for x in version_str.split("."))
                if major >= 3 and minor >= 10:
                    pythons.append((version_str, bare_python))
            except (OSError, subprocess.CalledProcessError):
                log.debug(
                    "python3-fallback-skip: path=%s reason=exec-or-parse-failed",
                    bare_python,
                )

    pythons.sort(key=lambda x: [int(p) for p in x[0].split(".")], reverse=True)
    return pythons


def print_colored_diff(
    old_content: str, new_content: str, fromfile: str, tofile: str
) -> bool:
    """Print a unified diff with ANSI colors.

    Returns True if there were changes, False otherwise.
    """
    red = "\033[31m"
    green = "\033[32m"
    cyan = "\033[36m"
    reset = "\033[0m"

    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
    )
    has_changes = False
    for line in diff:
        has_changes = True
        if line.startswith(("---", "+++", "@@")):
            print(cyan + line + reset, end="")
        elif line.startswith("-"):
            print(red + line + reset, end="")
        elif line.startswith("+"):
            print(green + line + reset, end="")
        else:
            print(line, end="")
    return has_changes


def appenv_settings_from_env() -> AppEnvSettings:
    """Read settings from environment variables."""
    # SPEC: fix-smell-appenv-verbose-truthy::smell-2 — truthy semantics: any
    # non-empty stripped value activates verbose; empty/whitespace no longer do.
    verbose = bool(os.environ.get("APPENV_VERBOSE", "").strip())
    extras_raw = os.environ.get("APPENV_EXTRAS") or ""
    # SPEC: fix-smells-extras-dedup-empty-empty-diff-silent::smell-1 — dedup
    # APPENV_EXTRAS to align with the ``--dep`` path (line ~1491).
    extras = _dedup_preserve_order(
        [e.strip() for e in extras_raw.split(",") if e.strip()]
    )
    basedir_str = os.environ.get("APPENV_BASEDIR")
    basedir = Path(basedir_str) if basedir_str else Path(__file__).parent

    return AppEnvSettings(
        verbose=verbose,
        extras=extras,
        basedir=basedir,
    )


# Internal diagnostics that expose Python plumbing — logging setup and the
# argparse Namespace repr carrying memory addresses. They stay in the file log
# for developers but are hidden from the user-facing verbose console.
# SPEC: fix-verbose-output::console-filter
_CONSOLE_HIDDEN_EVENTS = frozenset(
    {
        "build-env-dropped-pythonpath",
        "logging-configured",
        "no-compatible-python",
        "parsed-args",
        "parsed-args-remaining",
    }
)


class _ConsoleDiagnosticFilter(logging.Filter):
    """Hide internal diagnostics from the verbose console; keep them in file logs.

    The check inspects the message *topic* — the literal text before the first
    ``:`` in the format string — so it is stable regardless of the logged args
    and never has to render a raw Python object repr.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        topic = str(record.msg).split(":", 1)[0]
        return topic not in _CONSOLE_HIDDEN_EVENTS


class ColoredConsoleFormatter(logging.Formatter):
    """User-facing console formatter: dim arrow + message, no caller internals.

    Unlike the file handler, verbose console output omits ``funcName:lineno`` so
    users see operational steps (uv commands, venv creation, Python selection)
    instead of developer debug detail.
    """

    dim = "\033[2m"
    reset = "\033[0m"
    arrow = "→"

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        return f"{self.dim}{self.arrow}{self.reset} {message}"


def setup_logging(command_name: str, log_dir: Path, *, verbose: bool) -> None:
    """Setup command-specific logging with daily rotation.

    The file handler always records full caller detail (``funcName:lineno``) for
    developer post-mortem. The verbose console handler renders only user-relevant
    operational messages, hiding internal diagnostics and Python object reprs.
    """
    log_file = log_dir / f"{command_name}.log"

    for handler in log.handlers[:]:
        handler.close()
    log.handlers.clear()
    log.setLevel(logging.DEBUG)

    file_handler = TimedRotatingFileHandler(log_file, when="midnight", backupCount=7)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    log.addHandler(file_handler)

    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.addFilter(_ConsoleDiagnosticFilter())
        console_handler.setFormatter(ColoredConsoleFormatter("%(message)s"))
        log.addHandler(console_handler)

    log.debug("logging-configured: log_file=%s verbose=%s", log_file, verbose)


def main() -> None:
    settings = appenv_settings_from_env()

    ensure_best_python(settings.basedir)

    original_cwd = Path.cwd()
    appenv = AppEnv(original_cwd, settings)

    try:
        # Determine whether we're being called as appenv or as an application name
        application_name = Path(__file__).stem
        if application_name == "appenv":
            if len(sys.argv) > 1:
                remaining = sys.argv[1:]
                appenv.meta(remaining)
            else:
                # No arguments: show help directly instead of passing "help" as command
                appenv.meta([])
        else:
            remaining = sys.argv[1:]
            appenv.run(application_name, remaining)
    except CommandError as e:
        log.exception("command-failed: returncode=%d", e.returncode)
        sys.exit(e.returncode)


if __name__ == "__main__":  # pragma: no cover
    main()
