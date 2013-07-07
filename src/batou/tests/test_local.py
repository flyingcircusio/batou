from batou.local import main, LocalDeployment
from mock import patch, Mock
import pytest


@patch('sys.argv')
@patch('sys.stderr')
def test_no_args_exits_with_error(stderr, argv):
    with pytest.raises(SystemExit):
        main()


def test_no_components_no_cry():
    environment = Mock()
    environment.get_sorted_components.return_value = []
    mode = LocalDeployment(environment, 'asdf')
    mode()


def test_components_with_same_host_get_deployed_in_order():
    class SampleComponent(object):

        def __init__(self, log, host):
            self.log = log
            self.host = host

        def deploy(self):
            self.log.append(self)

    environment = Mock()
    host = Mock()
    environment.get_host.return_value = host
    log = []
    environment.get_sorted_components.return_value = components = [
        SampleComponent(log, host),
        SampleComponent(log, Mock()),
        SampleComponent(log, host)]
    LocalDeployment(environment, 'localhost')()
    assert [components[0], components[2]] == log
