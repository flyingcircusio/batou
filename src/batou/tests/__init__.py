# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

"""Batou unit and functional tests"""

import os.path
import unittest


class TestCase(unittest.TestCase):
    """TestCase base class with custom extensions."""

    def assertFileExists(self, filename):
        self.assertTrue(os.path.exists(filename),
                        'file %s does not exists but should' % filename)
