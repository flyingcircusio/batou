from batou.utils import cmd
import batou.lib.mercurial
import os.path
import pytest


@pytest.fixture(scope='function')
def repos_path(root):
    repos_path = os.path.join(root.environment.workdir_base, 'upstream')
    cmd('mkdir {dir}; cd {dir}; hg init;'
        'touch foo; hg add foo; hg commit -m "foo"'.format(dir=repos_path))
    return repos_path


@pytest.mark.slow
def test_runs_hg_to_clone_repository(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target='clone', revision='tip')
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/foo'))
    root.component.deploy()  # trigger verify


@pytest.mark.slow
def test_setting_branch_updates_on_incoming_changes(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target='clone', branch='default')
    root.component.deploy()
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/bar'))


@pytest.mark.slow
def test_branch_does_switch_branch(root, repos_path):
    cmd('cd {dir}; hg branch bar; hg ci -m "commit branch"'.format(
        dir=repos_path))
    root.component += batou.lib.mercurial.Clone(
        repos_path, target='clone', branch='bar')
    root.component.deploy()
    stdout, stderr = cmd('cd {workdir}/clone; hg branch'.format(
        workdir=root.workdir))
    assert 'bar' == stdout.strip()


@pytest.mark.slow
def test_set_revision_does_not_pull_when_revision_matches(root, repos_path):
    clone = batou.lib.mercurial.Clone(
        repos_path, target='clone', branch='default')
    root.component += clone
    root.component.deploy()
    revision = clone.current_revision
    clone.revision = revision
    clone.branch = None
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    stdout, stderr = cmd('cd {workdir}/clone; LANG=C hg incoming'.format(
        workdir=root.workdir))
    assert 'changeset:   1' in stdout


@pytest.mark.slow
def test_has_changes_counts_only_changes_to_tracked_files(root, repos_path):
    clone = batou.lib.mercurial.Clone(
        repos_path, target='clone', branch='default')
    root.component += clone
    root.component.deploy()
    assert not clone.has_changes
    cmd('touch {}/clone/bar'.format(root.workdir))
    assert not clone.has_changes
    cmd('cd {}/clone; hg add bar'.format(root.workdir))
    assert clone.has_changes


@pytest.mark.slow
def test_clean_clone_updates_on_incoming_changes(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target='clone', branch='default')
    root.component.deploy()
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    assert os.path.isfile(root.component.map('clone/bar'))


@pytest.mark.slow
def test_clone_with_changes_does_not_update(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target='clone', branch='default')
    root.component.deploy()
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    cmd('cd {dir}/clone; touch baz; hg addremove'.format(dir=root.workdir))
    root.component.deploy()
    assert not os.path.exists(root.component.map('clone/bar'))


@pytest.mark.slow
def test_clone_with_outgoing_changesets_does_not_update(root, repos_path):
    root.component += batou.lib.mercurial.Clone(
        repos_path, target='clone', branch='default')
    root.component.deploy()
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(
        dir=repos_path))
    cmd('cd {dir}/clone; touch baz; hg addremove; hg ci -m "commit"'.format(
        dir=root.workdir))
    root.component.deploy()
    assert not os.path.exists(root.component.map('clone/bar'))
