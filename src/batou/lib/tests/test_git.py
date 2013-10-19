from batou.utils import cmd
import batou.lib.git
import os.path
import pytest


@pytest.mark.slow
def test_runs_git_to_clone_repository(root):
    repos_path = os.path.join(root.environment.workdir_base, 'upstream')
    cmd('mkdir {dir}; cd {dir}; git init;'
        'touch foo; git add foo; git commit -am "foo"'.format(dir=repos_path))
    root.component += batou.lib.git.Clone(repos_path, target='clone')
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/foo'))
    root.component.deploy()  # trigger verify


@pytest.mark.slow
def test_git_offers_bbb_api(root):
    repos_path = os.path.join(root.environment.workdir_base, 'upstream')
    cmd('mkdir {dir}; cd {dir}; git init;'
        'touch foo; git add foo; git commit -am "foo"'.format(dir=repos_path))
    root.component += batou.lib.git.Clone('clone', source=repos_path)
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/foo'))
