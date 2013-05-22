# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import mock
import unittest


def prepare_test_component(component, require=[]):
    component.require = mock.Mock()
    component.require.return_value = require
    component.provide = mock.Mock()
    environment = mock.Mock()
    environment.service_user = 'test'
    environment.map = lambda x: x
    root = mock.Mock()
    root.workdir = '/tmp/batou-test/work-dir'
    service = mock.Mock()
    service.base = '/tmp/batou-test'
    host = mock.Mock()
    host.name = 'localhost'
    component.prepare(service, environment, host, root)


class TestNagiosServer(unittest.TestCase):

    def test_server_template(self):
        from ..nagios import NagiosServer, Service
        service = Service('http',
            command='http',
            args='-H localhost -u /login.html',
            depend_on=[('localhost', 'Supervisor')])
        prepare_test_component(service)
        server = NagiosServer('nagios')
        prepare_test_component(server, require=[service])
        server.environment.require.return_value = []
        self.assertEquals("""\
# Generated from template; don't edit manually!

#
# http
#
define service {
    use         generic-service
    host_name   localhost
    service_description http
    check_command http!-H localhost -u /login.html
    servicegroups direct
}

define servicedependency {
    use generic-servicedependency
    host_name localhost
    dependent_host_name localhost
    service_description Supervisor
    dependent_service_description http
}
""", server.sub_components[-1].content)

