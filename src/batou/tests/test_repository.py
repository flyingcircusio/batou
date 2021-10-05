import os
import subprocess

import mock
import pytest

import batou.utils
from batou.repository import MercurialRepository


def test_repository_hg_norepo(tmpdir):
    tmpdir = str(tmpdir)
    environment = mock.Mock()
    environment.root = tmpdir
    environment.base_dir = tmpdir
    os.chdir(tmpdir)

    with pytest.raises(batou.utils.CmdExecutionError):
        MercurialRepository(environment)

    subprocess.check_call(['hg', 'init'])
    MercurialRepository(environment)


def test_repository_hg_show_upstream(tmpdir):
    tmpdir = str(tmpdir)
    environment = mock.Mock()
    environment.root = tmpdir
    environment.base_dir = tmpdir
    os.chdir(tmpdir)
    subprocess.check_call(['hg', 'init'])

    repository = MercurialRepository(environment)
    environment.repository_url = 'asdf'
    assert repository.upstream == 'asdf'
    repository._upstream = None

    environment.repository_url = None
    with pytest.raises(batou.utils.CmdExecutionError):
        repository.upstream

    with open('.hg/hgrc', 'w') as f:
        f.write("""\
[paths]
foobar = 1234
""")

    with pytest.raises(AssertionError):
        repository.upstream

    with open('.hg/hgrc', 'w') as f:
        f.write("""\
[paths]
foobar = 1234
default = ssh://test@example.com/repos
""")

    assert repository.upstream == "ssh://test@example.com/repos"
    # Trigger cached access
    assert repository.upstream == "ssh://test@example.com/repos"


def test_repository_hg_verify(tmpdir):
    tmpdir = str(tmpdir)
    environment = mock.Mock()
    environment.root = tmpdir
    environment.base_dir = tmpdir
    environment.deployment.dirty = False

    os.chdir(tmpdir)

    subprocess.check_call(['hg', 'init'])

    subprocess.check_call(['hg', 'init', 'remote'])

    # Create a second repo as target
    with open('.hg/hgrc', 'w') as f:
        f.write("""\
[paths]
default = file:///{}/remote
""".format(tmpdir))

    repository = MercurialRepository(environment)
    # Clean repositories are fine
    repository.verify()

    with open('asdf', 'w') as f:
        f.write('foobar!')

    with pytest.raises(batou.utils.DeploymentError) as e:
        repository.verify()
    assert e.value.args[0] == "Uncommitted changes"

    subprocess.check_call(['hg', 'commit', '-A', '-m', 'test'])

    with pytest.raises(batou.utils.DeploymentError) as e:
        repository.verify()
    assert e.value.args[0] == "Outgoing changes"

    # We actually could deploy if we allow dirty deployments
    environment.deployment.dirty = True
    repository.verify()
    environment.deployment.dirty = False

    subprocess.check_call(['hg', 'push'])
    repository.verify()


def test_repository_hg_ship_verify_after_ship(tmpdir):
    tmpdir = str(tmpdir)
    environment = mock.Mock()
    environment.root = tmpdir
    environment.base_dir = tmpdir
    environment.deployment.dirty = False

    os.chdir(tmpdir)
    subprocess.check_call(['hg', 'init'])

    repository = MercurialRepository(environment)

    # We just want to ensure that the shipping validation code is fine
    def no_ship(host):
        pass

    repository._ship = no_ship

    host = mock.Mock()
    host.rpc.hg_update_working_copy.return_value = (
        '0000000000000000000000000000000000000000')
    repository.update(host)

    with open('asdf', 'w') as f:
        f.write('foobar')
    subprocess.check_call(['hg', 'add', 'asdf'])
    with pytest.raises(batou.RepositoryDifferentError):
        repository.update(host)

    environment.deployment.dirty = True
    repository.update(host)
