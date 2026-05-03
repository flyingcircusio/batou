"""zest.releaser hooks keeping batou-stubs in lockstep with batou.

``sync_stubs_release``/``sync_stubs_dev`` rewrite the stubs version and
the ``batou==`` pin in ``stubs/pyproject.toml`` during prerelease and
postrelease, so the change lands inside the release commits.
``publish_stubs`` builds and uploads batou-stubs from the tag checkout
right after batou's own upload.
"""

import importlib.metadata
import pathlib
import re

import pytest

from batou import release_hooks

REPO_ROOT = pathlib.Path(__file__).parents[3]
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
STUBS_PYPROJECT = REPO_ROOT / "stubs" / "pyproject.toml"

requires_repo = pytest.mark.skipif(
    not STUBS_PYPROJECT.exists(),
    reason="not running from a source checkout",
)


@pytest.fixture
def stubs_checkout(tmp_path):
    """Provide a working directory containing a copy of stubs/pyproject.toml."""
    stubs_dir = tmp_path / "stubs"
    stubs_dir.mkdir()
    (stubs_dir / "pyproject.toml").write_text(STUBS_PYPROJECT.read_text())
    return tmp_path


@requires_repo
def test_release__sync_stubs_release__rewrites_version_and_pin(
    stubs_checkout,
):
    """It writes new_version into the stubs version and the batou pin."""
    release_hooks.sync_stubs_release(
        {
            "workingdir": str(stubs_checkout),
            "name": "batou",
            "new_version": "2.8.0",
        }
    )

    content = (stubs_checkout / "stubs" / "pyproject.toml").read_text()
    assert 'version = "2.8.0"' in content
    assert '"batou==2.8.0"' in content
    assert "2.8.0.dev0" not in content


@requires_repo
def test_release__sync_stubs_dev__uses_dev_version(stubs_checkout):
    """It writes dev_version into the stubs version and the batou pin."""
    release_hooks.sync_stubs_dev(
        {
            "workingdir": str(stubs_checkout),
            "name": "batou",
            "dev_version": "2.9.0.dev0",
        }
    )

    content = (stubs_checkout / "stubs" / "pyproject.toml").read_text()
    assert 'version = "2.9.0.dev0"' in content
    assert '"batou==2.9.0.dev0"' in content


@requires_repo
def test_release__sync__ignores_foreign_packages(stubs_checkout):
    """It leaves the stubs alone when releasing another package."""
    before = (stubs_checkout / "stubs" / "pyproject.toml").read_text()

    release_hooks.sync_stubs_release(
        {
            "workingdir": str(stubs_checkout),
            "name": "some.other.package",
            "new_version": "1.0",
        }
    )

    assert (stubs_checkout / "stubs" / "pyproject.toml").read_text() == before


@pytest.mark.parametrize(
    ("group", "func"),
    [
        ("zest.releaser.prereleaser.middle", "sync_stubs_release"),
        ("zest.releaser.postreleaser.middle", "sync_stubs_dev"),
        ("zest.releaser.releaser.after", "publish_stubs"),
    ],
)
def test_release__entry_points__registered(group, func):
    """It resolves the zest.releaser hook groups to batou.release_hooks."""
    entry_points = importlib.metadata.entry_points(group=group)

    values = {ep.value for ep in entry_points}

    assert f"batou.release_hooks:{func}" in values


@requires_repo
def test_release__versions__root_stubs_pin_in_sync():
    """It keeps batou, batou-stubs and the pin on the same version."""
    stubs_content = STUBS_PYPROJECT.read_text()
    root_match = re.search(
        r'^version = "(.+)"$', ROOT_PYPROJECT.read_text(), re.MULTILINE
    )
    stubs_match = re.search(r'^version = "(.+)"$', stubs_content, re.MULTILINE)
    pin_match = re.search(r'"batou==([^"]+)"', stubs_content)
    assert root_match is not None
    assert stubs_match is not None
    assert pin_match is not None

    assert stubs_match.group(1) == root_match.group(1)
    assert pin_match.group(1) == root_match.group(1)


@requires_repo
def test_release__publish_stubs__aborts_on_version_mismatch(
    stubs_checkout, monkeypatch
):
    """It refuses to publish when the tag checkout stubs version drifts."""
    calls = []
    monkeypatch.setattr(release_hooks, "_build", lambda d: calls.append(d))
    monkeypatch.setattr(release_hooks, "_upload", lambda d: calls.append(d))

    with pytest.raises(RuntimeError):
        release_hooks.publish_stubs(
            {
                "name": "batou",
                "new_version": "9.9.9",
                "tagworkingdir": str(stubs_checkout),
            }
        )

    assert calls == []


@requires_repo
def test_release__publish_stubs__builds_and_uploads_tag_checkout(
    stubs_checkout, monkeypatch
):
    """It builds and uploads the tag-checkout stubs when versions match."""
    release_hooks.sync_stubs_release(
        {
            "workingdir": str(stubs_checkout),
            "name": "batou",
            "new_version": "9.9.9",
        }
    )
    calls = []
    monkeypatch.setattr(
        release_hooks, "_build", lambda d: calls.append(("build", d))
    )
    monkeypatch.setattr(
        release_hooks, "_upload", lambda d: calls.append(("upload", d))
    )

    release_hooks.publish_stubs(
        {
            "name": "batou",
            "new_version": "9.9.9",
            "tagworkingdir": str(stubs_checkout),
        }
    )

    assert calls == [
        ("build", stubs_checkout / "stubs"),
        ("upload", stubs_checkout / "stubs" / "dist"),
    ]
