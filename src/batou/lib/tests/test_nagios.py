from ..nagios import NagiosServer, Service


def test_server_template(root):
    service = Service(
        'http',
        command='http',
        args='-H localhost -u /login.html',
        depend_on=[('localhost', 'Supervisor')])
    root.component |= service
    server = NagiosServer()
    root.component += server
    assert """\
# Generated from template; don't edit manually!

#
# http
#
define service {
    use         generic-service
    host_name   host
    service_description http
    check_command http!-H localhost -u /login.html
    servicegroups direct
}

define servicedependency {
    use generic-servicedependency
    host_name localhost
    dependent_host_name host
    service_description Supervisor
    dependent_service_description http
}

""" == server.sub_components[-1].content
