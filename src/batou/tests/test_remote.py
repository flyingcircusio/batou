from batou.environment import Environment
from batou.deploy import Deployment
from batou.host import RemoteHost
from batou.utils import cmd
import pytest
import mock


@pytest.mark.slow
def test_remote_deployment_initializable(sample_service):
    cmd('hg init')
    with open('.hg/hgrc', 'w') as f:
        f.write('[paths]\ndefault=https://example.com')
    env = Environment('test-with-env-config')
    env.load()
    env.configure()
    Deployment(env, platform='', timeout=30, fast=False, dirty=False)


def test_remote_bundle_breaks_on_missing_head(sample_service):
    cmd('hg init')
    env = mock.Mock()
    env.base_dir = sample_service
    h = RemoteHost('asdf', env)
    from batou.repository import MercurialBundleRepository
    repository = MercurialBundleRepository(env)
    h.rpc = mock.Mock()
    h.rpc.hg_current_heads.return_value = []
    with pytest.raises(ValueError) as e:
        repository.update(h)
    assert e.value.message == (
        'Remote repository did not find any heads. '
        'Can not continue creating a bundle.')
