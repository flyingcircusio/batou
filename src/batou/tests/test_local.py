# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import unittest
import mock
from batou.local import main


class LocalTests(unittest.TestCase):

    @mock.patch('sys.argv')
    @mock.patch('sys.stderr')
    def test_no_args_exits_with_error(self, stderr, argv):
        with self.assertRaises(SystemExit):
            main()
