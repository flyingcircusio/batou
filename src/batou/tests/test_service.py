# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.service import Service, ServiceConfig
import batou.tests
import os.path
import unittest


class ServiceTests(unittest.TestCase):

    def test_datastructures_init(self):
        service1 = Service()
        service2 = Service()
        self.assertIsNot(service1.components, service2.components)
        self.assertIsNot(service1.environments, service2.environments)
