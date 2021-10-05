import os
import shutil

import pytest


@pytest.fixture()
def sample_service(tmpdir):
    shutil.copytree(
        os.path.dirname(__file__) + "/fixture/sample_service",
        str(tmpdir / "sample_service"))
    target = str(tmpdir / "sample_service")
    os.chdir(target)
    return target


@pytest.fixture(autouse=True)
def ensure_git_config(monkeypatch):
    monkeypatch.setitem(os.environ, "GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setitem(os.environ, "GIT_AUTHOR_NAME", "Mr. U. Test")
    monkeypatch.setitem(os.environ, "GIT_COMMITTER_EMAIL", "test@example.com")
    monkeypatch.setitem(os.environ, "GIT_COMMITTER_NAME", "Mr. U. Test")
