# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import unittest
from batou.service import Service


class ServiceTests(unittest.TestCase):

    def test_datastructures_init(self):
        service1 = Service()
        service2 = Service()
        self.assertIsNot(service1.components, service2.components)
        self.assertIsNot(service1.environments, service2.environments)
