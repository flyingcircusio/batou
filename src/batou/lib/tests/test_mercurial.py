from batou.utils import cmd
import batou.lib.mercurial
import os.path
import pytest


@pytest.mark.slow
def test_runs_hg_to_clone_repository(root):
    repos_path = os.path.join(root.environment.workdir_base, 'upstream')
    cmd('mkdir {dir}; cd {dir}; hg init;'
        'touch foo; hg add foo; hg commit -m "foo"'.format(dir=repos_path))
    root.component += batou.lib.mercurial.Clone(
        repos_path, target='clone', revision='tip')
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/foo'))
    root.component.deploy()  # trigger verify
