from StringIO import StringIO
from batou.local import main, AutoMode, BatchMode
from mock import patch, Mock
import unittest


class LocalTests(unittest.TestCase):

    @patch('sys.argv')
    @patch('sys.stderr')
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
        environment = Mock()
        environment.get_sorted_components.return_value = []
        mode = AutoMode(environment, 'asdf')
        mode()

    def test_components_with_same_host_get_deployed_in_order(self):
        environment = Mock()
        host = Mock()
        environment.get_host.return_value = host
        log = []
        environment.get_sorted_components.return_value = components = [
                TestComponent(log, host),
                TestComponent(log, Mock()),
                TestComponent(log, host)]
        AutoMode(environment, 'localhost')()
        self.assertListEqual([components[0], components[2]], log)


class BatchModeTests(unittest.TestCase):

    def test_configure_command_configures_environment(self):
        environment = Mock()
        mode = BatchMode(environment, 'localhost')
        mode.cmd_configure()
        self.assertTrue(environment.configure.called)

    def test_deploy_command_deploys_named_component(self):
        environment = Mock()
        log = []
        mode = BatchMode(environment, 'localhost')
        mode.host = dict(asdf=TestComponent(log, Mock()),
                         bsdf=TestComponent(log, Mock()))
        mode.cmd_deploy('asdf')
        self.assertListEqual([mode.host['asdf']], log)

    @patch('batou.utils.input')
    def test_batchmode_input_triggers_and_output(self, input):
        environment = Mock()
        mode = BatchMode(environment, 'localhost')
        mode.output = StringIO()

        def input_mock():
            try:
                value = input_script.pop(0)
            except IndexError:
                raise EOFError
            return value

        input_script = ['set component key value',
                        'configure',
                        'deploy component',
                        '',
                        'asdf']
        mode.input = input_mock
        mode.cmd_set = Mock()
        mode.cmd_configure = Mock()
        mode.cmd_deploy = Mock()
        mode()
        mode.cmd_set.assert_called_with('component key value')
        mode.cmd_configure.assert_called_with()
        mode.cmd_deploy.assert_called_with('component')

        mode.cmd_set.side_effect = Exception('Failed set')
        input_script = ['set asdf']
        mode()
        self.assertEquals('OK\nOK\nOK\nERROR\n', mode.output.getvalue())
