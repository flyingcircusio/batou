from batou.environment import Environment
from batou.remote import RemoteDeployment
from batou.utils import cmd
import pytest


@pytest.mark.slow
def test_remote_deployment_initializable(sample_service):
    cmd('hg init')
    with open('.hg/hgrc', 'w') as f:
        f.write('[paths]\ndefault=https://example.com')
    env = Environment('test-with-env-config')
    env.load()
    env.configure()
    RemoteDeployment(env, False)
