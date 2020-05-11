import batou.component
import batou.lib.service
import pytest


@pytest.fixture
def deploy_platform():
    return 'test'


@pytest.yield_fixture
def service(root, tmpdir, request, deploy_platform):
    old_platforms = getattr(batou.lib.service.Service, '_platforms', {})
    if old_platforms:
        del batou.lib.service.Service._platforms

    root.host.platform = deploy_platform

    @batou.component.platform('test', batou.lib.service.Service)
    class TestPlatformService(batou.component.Component):

        def start(self):
            service._platform_started = True

    @batou.component.platform('nostart', batou.lib.service.Service)
    class NoStartPlatformService(batou.component.Component):
        pass

    batou.lib.service.Service._add_platform('test', TestPlatformService)

    service = batou.lib.service.Service(
        'touch {}/called'.format(tmpdir))
    service._platform_started = False
    root.component += service
    root.component.deploy()
    yield service
    batou.lib.service.Service._platforms = old_platforms


def test_start_delegates_to_platform_component(service, tmpdir):
    service.start()
    # The platform specific start() was called
    assert service._platform_started
    # The default implementation was not called
    assert not tmpdir.join('called').check()


@pytest.mark.parametrize('deploy_platform', ['another'])
def test_start_runs_executable_if_no_platform_component(service, tmpdir):
    service.start()
    assert tmpdir.join('called').check()


@pytest.mark.parametrize('deploy_platform', ['nostart'])
def test_start_runs_executable_if_no_platform_specific_start(service, tmpdir):
    service.start()
    assert tmpdir.join('called').check()
