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
    cmd('cd {dir}; touch bar; hg addremove; hg ci -m "commit"'.format(dir=repos_path))
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/bar'))