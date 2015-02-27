from batou.environment import Environment
from batou.remote import RemoteDeployment, RemoteHost
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
    RemoteDeployment(env, False)


def test_remote_bundle_breaks_on_missing_head(sample_service):
    h = RemoteHost(None, None)
    h.rpc = mock.Mock()
    h.rpc.current_heads.return_value = []
    with pytest.raises(ValueError) as e:
        h.update_hg_bundle()
    assert e.value.message == (
        'Remote repository did not find any heads. '
        'Can not continue creating a bundle.')
