from batou.utils import cmd
import batou.lib.git
import os.path
import pytest


def _repos_path(root, name):
    repos_path = os.path.join(root.environment.workdir_base, name)
    cmd('mkdir {dir}; cd {dir}; git init;'
        'git config user.name Jenkins;'
        'git config user.email jenkins@example.com;'
        'touch foo; git add .;'
        'git commit -am "foo"'.format(
            dir=repos_path))
    return repos_path


@pytest.fixture(scope='function')
def repos_path(root, name='upstream'):
    return _repos_path(root, name)


@pytest.fixture(scope='function')
def repos_path2(root, name='upstream2'):
    return _repos_path(root, name)


@pytest.mark.slow
def test_runs_git_to_clone_repository(root, repos_path):
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/foo'))
    root.component.deploy()  # trigger verify


@pytest.mark.slow
def test_directly_after_clone_nothing_is_merged(root, repos_path):
    # When a Clone is confirgured with a branch, the general gesture for
    # updating is "git merge origin/branch", but directly after cloning, the
    # Clone is still on master, so this would try to merge the configured
    # branch into master, which is wrong.
    cmd('cd {dir}; git checkout -b other; touch bar; echo qux > foo;'
        'git add .; git commit -am "other";'
        # Set up branches to be different, so we see that no merge takes place
        'git checkout master; '
        'echo one > foo; git add . ; git commit -am "foo master";'.format(
            dir=repos_path))
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='other')
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/bar'))


@pytest.mark.slow
def test_setting_branch_updates_on_incoming_changes(root, repos_path):
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component.deploy()
    cmd('cd {dir}; touch bar; git add .; git commit -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/bar'))


@pytest.mark.slow
def test_setting_revision_updates_on_incoming_changes(root, repos_path):
    cmd('cd {dir}; touch bar; git add .; git commit -m "commit2"'.format(
        dir=repos_path))
    commit1, _ = cmd('cd {dir}; git rev-parse HEAD^'.format(dir=repos_path))
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', revision=commit1)
    root.component.deploy()
    cmd('cd {dir}; touch qux; git add .; git commit -m "commit3"'.format(
        dir=repos_path))
    root.component.deploy()  # Our main assertion: Nothing breaks here
    assert not os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/qux'))


@pytest.mark.slow
def test_branch_does_switch_branch(root, repos_path):
    cmd('cd {dir}; touch bar; git add .; git checkout -b bar;'
        'git commit -m "commit branch"'.format(dir=repos_path))
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='bar')
    root.component.deploy()
    stdout, stderr = cmd(
        'cd {workdir}/clone; git rev-parse --abbrev-ref HEAD'.format(
            workdir=root.workdir))
    assert 'bar' == stdout.strip()


@pytest.mark.slow
def test_has_changes_counts_changes_to_tracked_files(root, repos_path):
    clone = batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component += clone
    root.component.deploy()
    assert not clone.has_changes()
    cmd('touch {}/clone/bar'.format(root.workdir))
    cmd('cd {}/clone; git add bar'.format(root.workdir))
    assert clone.has_changes()


@pytest.mark.slow
def test_has_changes_counts_untracked_files_as_changes(root, repos_path):
    clone = batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component += clone
    root.component.deploy()
    assert not clone.has_changes()
    cmd('touch {}/clone/bar'.format(root.workdir))
    assert clone.has_changes()


@pytest.mark.slow
def test_clean_clone_updates_on_incoming_changes(root, repos_path):
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component.deploy()
    cmd('cd {dir}; touch bar; git add .; git commit -m "commit"'.format(
        dir=repos_path))
    root.component.deploy()
    assert os.path.isfile(root.component.map('clone/bar'))


@pytest.mark.slow
def test_changes_lost_on_update_with_incoming(root, repos_path):
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component.deploy()
    cmd('cd {dir}; touch bar; git add .; git commit -m "commit"'.format(
        dir=repos_path))
    cmd('cd {dir}/clone; echo foobar >foo'.format(dir=root.workdir))
    root.component.deploy()
    assert os.path.exists(root.component.map('clone/bar'))
    assert not open(root.component.map('clone/foo')).read()


@pytest.mark.slow
def test_changes_lost_on_update_without_incoming(root, repos_path):
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component.deploy()
    cmd('cd {dir}/clone; echo foobar >foo'.format(dir=root.workdir))
    root.component.deploy()
    assert not open(root.component.map('clone/foo')).read()


@pytest.mark.slow
def test_untracked_files_are_removed_on_update(root, repos_path):
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='master')
    root.component.deploy()
    cmd('cd {dir}/clone; mkdir bar; echo foobar >bar/baz'.format(
        dir=root.workdir))
    root.component.deploy()
    assert not os.path.exists(root.component.map('clone/bar/baz'))


@pytest.mark.slow
def test_clean_clone_vcs_update_false_leaves_changes_intact(root, repos_path):
    root.component += batou.lib.git.Clone(
        repos_path, target='clone', branch='master', vcs_update=False)
    root.component.deploy()
    cmd('cd {dir}; echo foobar >foo; touch bar; git add .; '
        'git commit -m "commit"'.format(dir=repos_path))
    cmd('cd {dir}/clone; echo asdf >foo'.format(dir=root.workdir))
    root.component.deploy()
    assert 'asdf\n' == open(root.component.map('clone/foo')).read()
    assert not os.path.exists(root.component.map('clone/bar'))


@pytest.mark.slow
def test_changed_remote_is_updated(root, repos_path, repos_path2):
    git = batou.lib.git.Clone(repos_path, target='clone', branch='master')
    root.component += git

    # Fresh, unrelated repo
    cmd('cd {dir}; echo baz >bar; git add .;'
        'git commit -m "commit"'.format(dir=repos_path2))

    root.component.deploy()
    assert not os.path.exists(root.component.map('clone/bar'))
    git.url = repos_path2
    root.component.deploy()
    assert os.path.exists(root.component.map('clone/bar'))


@pytest.mark.slow
def test_clone_into_workdir_works(root, repos_path, repos_path2):
    git = batou.lib.git.Clone(repos_path, branch='master')
    with open(root.component.map('asdf'), 'w') as f:
        f.write('foo')
    root.component += git
    root.component.deploy()
    assert not os.path.exists(root.component.map('asdf'))
