from batou.utils import cmd
import batou.lib.mercurial
import os.path
import pytest


@pytest.fixture(scope="function")
def repos_path(root):
    repos_path = os.path.join(root.environment.workdir_base, "upstream")
    cmd("mkdir {dir}; cd {dir}; hg init;"
        'touch foo; hg add foo; hg commit -m "foo"'.format(dir=repos_path))
    return repos_path


@pytest.mark.slow
def test_runs_hg_to_clone_repository(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", revision="tip")
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, "mycomponent/clone/foo"))
    root.component.deploy()  # trigger verify


@pytest.mark.slow
def test_setting_branch_updates_on_incoming_changes(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component.deploy()
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, "mycomponent/clone/bar"))


@pytest.mark.slow
def test_branch_does_switch_branch(root, repos_path):
    cmd('cd {dir}; hg branch bar; hg ci -m "commit branch"'.format(
        dir=repos_path))
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="bar")
    root.component.deploy()
    stdout, stderr = cmd(
        "cd {workdir}/clone; hg branch".format(workdir=root.workdir))
    assert "bar" == stdout.strip()


@pytest.mark.slow
def test_set_revision_does_not_pull_when_revision_matches(root, repos_path):
    clone = batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component += clone
    root.component.deploy()
    revision = clone.current_revision()
    clone.revision = revision
    clone.branch = None
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    stdout, stderr = cmd(
        "cd {workdir}/clone; LANG=C hg incoming".format(workdir=root.workdir))
    assert "changeset:   1" in stdout


@pytest.mark.slow
def test_set_revision_does_not_change_when_long_revision_matches(
        root, repos_path):
    clone = batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component += clone
    root.component.deploy()
    stdout, stderr = clone.cmd(
        clone.expand(
            "LANG=C hg --cwd {{component.target}} --debug tip | head -n1"))
    _, _, revision = stdout.split(":")
    clone.revision = revision.strip()
    clone.branch = None
    root.component.deploy()
    assert not clone.changed


@pytest.mark.slow
def test_has_changes_counts_changes_to_tracked_files(root, repos_path):
    clone = batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component += clone
    root.component.deploy()
    assert not clone.has_changes()
    cmd("touch {}/clone/bar".format(root.workdir))
    cmd("cd {}/clone; hg add bar".format(root.workdir))
    assert clone.has_changes()


@pytest.mark.slow
def test_has_changes_counts_untracked_files_as_changes(root, repos_path):
    clone = batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component += clone
    root.component.deploy()
    assert not clone.has_changes()
    cmd("touch {}/clone/bar".format(root.workdir))
    assert clone.has_changes()


@pytest.mark.slow
def test_clean_clone_updates_on_incoming_changes(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component.deploy()
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    assert os.path.isfile(root.component.map("clone/bar"))


@pytest.mark.slow
def test_changes_lost_on_update_with_incoming(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component.deploy()
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    cmd("cd {dir}/clone; echo foobar >foo".format(dir=root.workdir))
    root.component.deploy()
    assert os.path.exists(root.component.map("clone/bar"))
    with open(root.component.map("clone/foo")) as f:
        assert not f.read()


@pytest.mark.slow
def test_untracked_files_are_removed_on_update(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component.deploy()
    cmd("cd {dir}/clone; mkdir bar; echo foobar >bar/baz".format(
        dir=root.workdir))
    root.component.deploy()
    assert not os.path.exists(root.component.map("clone/bar/baz"))


@pytest.mark.slow
def test_changes_lost_on_update_without_incoming(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default")
    root.component.deploy()
    cmd("cd {dir}/clone; echo foobar >foo".format(dir=root.workdir))
    root.component.deploy()
    with open(root.component.map("clone/foo")) as f:
        assert not f.read()


@pytest.mark.slow
def test_clean_clone_vcs_update_false_leaves_changes_intact(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target="clone", branch="default", vcs_update=False)
    root.component.deploy()
    cmd("cd {dir}; echo foobar >foo; touch bar; hg addremove; "
        'hg ci -m "commit"'.format(dir=repos_path))
    cmd("cd {dir}/clone; echo asdf >foo".format(dir=root.workdir))
    root.component.deploy()
    with open(root.component.map("clone/foo")) as f:
        assert "asdf\n" == f.read()
    assert not os.path.exists(root.component.map("clone/bar"))
