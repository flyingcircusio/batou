from batou.component import Component, RootComponent, platform
from mock import Mock
import batou
import os
import os.path
import pytest
import time


class SampleComponent(Component):
    updated = False
    needs_update = True

    def verify(self):
        if self.needs_update:
            raise batou.UpdateNeeded()

    def update(self):
        self.updated = True


def test_init_with_no_arguments_creates_plain_component():
    component = Component()
    # Lazy initialized attribute
    assert not hasattr(component, 'sub_components')


def test_plain_component_runs_noop_configure_verify_update():
    component = Component()
    component.configure()
    component.verify()
    component.update()


def test_init_component_with_namevar_uses_first_argument():
    class SampleComponent(Component):
        namevar = 'asdf'
    component = SampleComponent('foobar')
    assert 'foobar' == component.asdf


def test_init_component_with_namevar_fails_without_argument():
    class SampleComponent(Component):
        namevar = 'asdf'
    with pytest.raises(ValueError):
        SampleComponent()


def test_init_keyword_args_update_dict():
    component = Component(foobar=1)
    assert 1 == component.foobar


def test_remote_bootstrap():
    # The default remote bootstrap doesn't do anything: just exercise that
    # it's there.  This could go away once we start testing the remoting
    # code.
    component = Component(Mock())
    component.remote_bootstrap(Mock())


def test_prepare_sets_up_vars():
    service = Mock()
    environment = Mock()
    host = Mock()
    root = Mock()
    parent = Mock()
    component = Component()
    component.prepare(
        service, environment, host, root, parent)
    assert service == component.service
    assert environment == component.environment
    assert host == component.host
    assert root == component.root
    assert parent == component.parent


def test_prepare_calls_configure():
    component = Component()
    component.configure = Mock()
    component.prepare(None, Mock(), None, None)
    assert component.configure.called


def test_prepare_configures_applicable_platforms_as_subcomponents():
    class MyComponent(Component):
        pass

    class MyOtherComponent(MyComponent):
        pass

    @platform('testplatform', MyComponent)
    class MyPlatform(Component):
        pass

    @platform('otherplatform', MyComponent)
    class MyOtherPlatform(Component):
        pass

    environment = Mock()
    environment.platform = 'testplatform'
    component = MyComponent()
    component.prepare(None, environment, None, None)
    assert 1 == len(component.sub_components)
    assert isinstance(component.sub_components[0], MyPlatform)
    # Because we currently have no defined behaviour about this
    # I'm playing this rather safe: a sub-class of a component does not
    # automatically get to have the same platform components applied.
    other_component = MyOtherComponent()
    other_component.prepare(None, environment, None, None)
    assert 0 == len(other_component.sub_components)


def test_deploy_empty_component_runs_without_error():
    component = Component()
    component.prepare(None, Mock(), None, None)
    component.deploy()


def test_deploy_update_performed_if_needed():
    component = SampleComponent(needs_update=True)
    component.prepare(None, Mock(), None, None)
    component.deploy()
    assert component.updated


def test_deploy_update_not_performed_if_not_needed():
    component = SampleComponent(needs_update=False)
    component.prepare(None, Mock(), None, None)
    component.deploy()
    assert not component.updated


def test_sub_components_are_deployed_first():
    log = []

    class MyComponent(Component):
        namevar = 'id'

        def verify(self):
            log.append('{}:verify'.format(self.id))
            raise batou.UpdateNeeded()

        def update(self):
            log.append('{}:update'.format(self.id))
    top = MyComponent('1')
    top.prepare(None, Mock(), None, None)
    top += MyComponent('2')
    top.deploy()
    assert [u'2:verify', u'2:update', u'1:verify', u'1:update'] == log


def test_adding_subcomponents_configures_them_immediately():
    class MyComponent(Component):
        configured = False

        def configure(self):
            self.configured = True
    component = Component()
    component.prepare(None, Mock(), None, None)
    my = MyComponent()
    component += my
    assert my.configured


# AFIC = assert file is current
def test_afic_raises_if_nonexisting_file():
    component = Component()
    with pytest.raises(batou.UpdateNeeded):
        component.assert_file_is_current('idonotexist')


def test_afic_doesnt_raise_if_file_exists_but_no_reference_is_given():
    component = Component()
    component.assert_file_is_current(__file__)


def test_afic_raises_if_file_isolder_than_reference(tmpdir):
    component = Component()
    with pytest.raises(batou.UpdateNeeded):
        component.assert_file_is_current(__file__, [str(tmpdir)])


# ANSC = assert no subcomponent changes
def test_ansc_raises_if_subcomponent_changed():
    c = Component()
    c.prepare(None, Mock(), 'localhost', None)
    c2 = Component()
    c += c2
    c2.changed = True
    with pytest.raises(batou.UpdateNeeded):
        c.assert_no_subcomponent_changes()


def test_ansc_does_not_raise_if_no_subcomponent_changed():
    c = Component()
    c.prepare(None, Mock(), 'localhost', None)
    c2 = Component()
    c += c2
    c2.changed = False
    c.assert_no_subcomponent_changes()


def test_cmd_returns_output():
    c = Component()
    assert ('1\n', '') == c.cmd('echo 1')


def test_cmd_raises_if_error():
    c = Component()
    with pytest.raises(RuntimeError):
        c.cmd('non-existing-command')


def test_cmd_returns_output_if_ignore_returncode():
    c = Component()
    out, err = c.cmd('echo important output && false', silent=True,
                     ignore_returncode=True)
    assert 'important output\n' == out


def test_touch_creates_new_file(tmpdir):
    reference = str(tmpdir / 'reference')
    assert not os.path.exists(reference)
    c = Component()
    c.touch(reference)
    assert os.path.exists(reference)


def test_touch_updates_mtime_leaves_content_intact(tmpdir):
    reference = str(tmpdir / 'reference')
    with open(reference, 'w') as r:
        r.write('Hello world')
    mtime = os.stat(reference).st_mtime
    c = Component()
    time.sleep(1)
    c.touch(reference)
    assert mtime < os.stat(reference).st_mtime
    with open(reference, 'r') as r:
        assert 'Hello world' == r.read()


def test_expand():
    c = Component()
    c.prepare(None, Mock(), 'localhost', None)
    assert 'Hello localhost' == c.expand('Hello {{host}}')


def test_templates(tmpdir):
    sample = str(tmpdir / 'sample')
    with open(sample, 'w') as template:
        template.write('Hello {{host}}')
    c = Component()
    c.prepare(None, Mock(), 'localhost', None)
    assert 'Hello localhost\n' == c.template(sample)


def test_chdir_contextmanager_is_stackable():
    outer = os.getcwd()
    inner1 = os.path.join(os.path.dirname(__file__), 'fixture')
    inner2 = os.path.join(os.path.dirname(__file__))
    c = Component()
    with c.chdir(inner1):
        assert inner1 == os.getcwd()
        with c.chdir(inner2):
            assert inner2 == os.getcwd()
        assert inner1 == os.getcwd()
    assert outer == os.getcwd()


def test_root_component_computes_working_dir():
    c = Component()
    host = Mock()
    host.environment.workdir_base = 'path-to-service/work'
    root = RootComponent('test', c, c.__class__, host, None)
    c.root = root
    assert root.workdir == 'path-to-service/work/test'
    assert c.workdir == 'path-to-service/work/test'


def test_root_component_creates_working_dir_runs_component_deploy(tmpdir):
    d = str(tmpdir)

    class MyComponent(Component):
        pass
    c = MyComponent
    c.deploy = Mock()
    host = Mock()
    host.environment.workdir_base = d + '/work'
    host.environment.overrides = {}
    root = RootComponent('test', c, c.__class__, host, None)
    assert not os.path.isdir(root.workdir)
    root.prepare()
    root.deploy()
    assert os.path.isdir(root.workdir)
    cwd = os.getcwd()
    # Need to ensure we resolve symlinks: on OS x /var/tmp may lead to
    # /private/...
    assert os.path.realpath(cwd) == os.path.realpath(root.workdir)
    assert c.deploy.called


def test_cmd_execution_failed_gives_command_in_exception():
    c = Component()
    with pytest.raises(RuntimeError) as e:
        c.cmd('asdf')
    assert str(e.value[0]) == 'Command "asdf" returned unsuccessfully.'
    assert e.value[1] == 127


def test_cmd_should_not_stop_if_process_expects_input():
    c = Component()
    stdout, stderr = c.cmd('cat')
    # The assertion is, that the test doesn't get stuck .
