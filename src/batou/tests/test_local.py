import unittest
import mock
from batou.local import main, AutoMode


class LocalTests(unittest.TestCase):

    @mock.patch('sys.argv')
    @mock.patch('sys.stderr')
    def test_no_args_exits_with_error(self, stderr, argv):
        with self.assertRaises(SystemExit):
            main()


class TestComponent(object):

    def __init__(self, log, host):
        self.log = log
        self.host = host

    def deploy(self):
        self.log.append(self)


class AutoModeTests(unittest.TestCase):

    def test_no_components_no_cry(self):
        environment = mock.Mock()
        environment.ordered_components = []
        mode = AutoMode(environment, 'asdf')
        mode()

    def test_components_with_same_host_get_deployed_in_order(self):
        environment = mock.Mock()
        host = mock.Mock()
        environment.get_host.return_value = host
        log = []
        environment.ordered_components = components = [
                TestComponent(log, host),
                TestComponent(log, mock.Mock()),
                TestComponent(log, host)]
        AutoMode(environment, 'asdf')()
        self.assertListEqual([components[0], components[2]], log)
