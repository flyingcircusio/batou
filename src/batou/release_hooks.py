"""zest.releaser hooks keeping batou-stubs in lockstep with batou.

Registered as entry points in pyproject.toml:

* ``zest.releaser.prereleaser.middle`` -- before the version rewrite
  and the "Preparing release" commit: sync stubs to the final version.
* ``zest.releaser.postreleaser.middle`` -- before the "Back to
  development" commit: sync stubs to the next dev version.
* ``zest.releaser.releaser.after`` -- after batou's upload: build
  batou-stubs from the tag checkout and upload it via twine, using the
  same credential path (.pypirc / TWINE_*) as the batou upload.

The middle hooks fire before ``git commit -a``, so the synced
stubs/pyproject.toml lands inside the release commits. Rewrite is
line-based (no tomllib: batou supports Python 3.10).
"""

import glob
import pathlib
import re
import subprocess
import sys


def _sync_stubs(workingdir, version):
    """Write `version` into stubs/pyproject.toml (version + batou pin)."""
    path = pathlib.Path(workingdir) / "stubs" / "pyproject.toml"
    content = path.read_text()
    content = re.sub(
        r'^version = ".*"$',
        f'version = "{version}"',
        content,
        count=1,
        flags=re.M,
    )
    content = re.sub(r'"batou==[^"]*"', f'"batou=={version}"', content, count=1)
    path.write_text(content)


def sync_stubs_release(data):
    """Sync batou-stubs to the version being released (prerelease step)."""
    if data.get("name") != "batou":
        return
    _sync_stubs(data["workingdir"], data["new_version"])


def sync_stubs_dev(data):
    """Sync batou-stubs to the next dev version (postrelease step)."""
    if data.get("name") != "batou":
        return
    _sync_stubs(data["workingdir"], data["dev_version"])


def _stubs_version(stubs_dir):
    content = (pathlib.Path(stubs_dir) / "pyproject.toml").read_text()
    match = re.search(r'^version = "(.+)"$', content, flags=re.M)
    assert match is not None
    return match.group(1)


def _build(stubs_dir):
    """Build sdist + wheel of batou-stubs into stubs_dir/dist."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--outdir",
            str(pathlib.Path(stubs_dir) / "dist"),
        ],
        cwd=str(stubs_dir),
        check=True,
    )


def _upload(dist_dir):
    """Upload the built distributions via twine (same credentials as batou)."""
    files = sorted(glob.glob(str(pathlib.Path(dist_dir) / "*")))
    subprocess.run(["twine", "upload", *files], check=True)


def publish_stubs(data):
    """Build and upload batou-stubs from the tag checkout (release step)."""
    if data.get("name") != "batou":
        return
    stubs_dir = pathlib.Path(data["tagworkingdir"]) / "stubs"
    expected = data["new_version"]
    actual = _stubs_version(stubs_dir)
    if actual != expected:
        raise RuntimeError(
            f"batou-stubs version {actual} does not match the released "
            f"batou version {expected}; refusing to publish stale stubs."
        )
    _build(stubs_dir)
    _upload(stubs_dir / "dist")
