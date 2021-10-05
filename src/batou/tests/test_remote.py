import mock
import pytest

from batou.deploy import Deployment
from batou.environment import Environment
from batou.host import RemoteHost
from batou.utils import cmd


@pytest.mark.slow
def test_remote_deployment_initializable(sample_service):
    cmd("hg init")
    with open(".hg/hgrc", "w") as f:
        f.write("[paths]\ndefault=https://example.com")
    env = Environment("test-with-env-config")
    env.load()
    env.configure()
    Deployment(env, platform="", jobs=1, timeout=30, dirty=False)


def test_remote_bundle_breaks_on_missing_head(sample_service):
    cmd("hg init")
    env = mock.Mock()
    env.base_dir = sample_service
    h = RemoteHost("asdf", env)
    from batou.repository import MercurialBundleRepository

    repository = MercurialBundleRepository(env)
    h.rpc = mock.Mock()
    h.rpc.hg_current_heads.return_value = []
    with pytest.raises(ValueError) as e:
        repository.update(h)
    assert e.value.args == ("Remote repository did not find any heads. "
                            "Can not continue creating a bundle.", )


def test_remotehost_start(sample_service):
    env = Environment("test-with-env-config")
    env.load()
    env.configure()
    h = RemoteHost("asdf", env)
    h.connect = mock.Mock()
    h.rpc = mock.Mock()
    h.rpc.ensure_base.return_value = '/tmp'
    h.start()
