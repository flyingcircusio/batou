from batou.service import ServiceConfig
import os
import os.path
import unittest


class TestEndToEndScenarios(unittest.TestCase):

    def test_service_early_resource(self):
        config = ServiceConfig(os.path.dirname(__file__) +
                   '/fixture/service_early_resource', ['dev'])
        config.scan()
        env = config.service.environments['dev']
        env.configure()
        self.assertEquals(['127.0.0.1:9000'], env.resources.get('zeo'))
