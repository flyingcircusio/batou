from batou.utils import cmd
import batou.lib.svn
import os.path
import pytest


@pytest.mark.slow
def test_runs_svn_to_clone_repository(root):
    repos_path = os.path.join(root.environment.workdir_base, 'repos')
    cmd('svnadmin create ' + repos_path)
    cmd('svn checkout file://{dir} upstream; cd upstream;'
        'touch foo; svn add foo; svn commit -m "bar"'.format(dir=repos_path))
    root.component += batou.lib.svn.Checkout(
        'file://' + repos_path, target='clone', revision='head')
    root.component.deploy()
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, 'mycomponent/clone/foo'))
    root.component.deploy()  # trigger verify
