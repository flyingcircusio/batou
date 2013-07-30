from batou.environment import Environment
import os.path


def test_service_early_resource():
    env = Environment(
        'dev',
        os.path.dirname(__file__)+'/fixture/service_early_resource')
    env.load()
    env.configure()
    assert env.resources.get('zeo') == ['127.0.0.1:9000']
