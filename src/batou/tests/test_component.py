from batou.component import Component, RootComponent, platform
from mock import Mock
import batou
import os
import os.path
import pytest


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


def test_prepare_sets_up_vars(root):
    root.prepare()
    assert root.component.environment is root.environment
    assert root.component.host is root.host
    assert root.component.root is root
    assert root.component.parent is None


def test_prepare_calls_configure():
    component = Component()
    component.configure = Mock()
    component.prepare(Mock(), Mock())
    assert component.configure.called


def test_prepare_configures_applicable_platforms_as_subcomponents(root):
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

    root.environment.platform = 'testplatform'
    component = MyComponent()
    root.component += component
    assert 1 == len(component.sub_components)
    assert isinstance(component.sub_components[0], MyPlatform)
    # Because we currently have no defined behaviour about this
    # I'm playing this rather safe: a sub-class of a component does not
    # automatically get to have the same platform components applied.
    other_component = MyOtherComponent()
    root.component += other_component
    assert 0 == len(other_component.sub_components)


def test_deploy_empty_component_runs_without_error(root):
    root.component.deploy()


def test_deploy_update_performed_if_needed(root):
    root.prepare()
    component = SampleComponent(needs_update=True)
    root.component += component
    root.component.deploy()
    assert component.updated


def test_deploy_update_not_performed_if_not_needed(root):
    root.prepare()
    component = SampleComponent(needs_update=False)
    root.component += component
    root.component.deploy()
    assert not component.updated


def test_sub_components_are_deployed_first(root):
    log = []

    class MyComponent(Component):
        namevar = 'id'

        def verify(self):
            log.append('{}:verify'.format(self.id))
            raise batou.UpdateNeeded()

        def update(self):
            log.append('{}:update'.format(self.id))

    c1 = MyComponent('1')
    root.component += c1
    c1 += MyComponent('2')
    root.component.deploy()
    assert [u'2:verify', u'2:update', u'1:verify', u'1:update'] == log


def test_adding_subcomponents_configures_them_immediately(root):
    class MyComponent(Component):
        configured = False

        def configure(self):
            self.configured = True
    my = MyComponent()
    root.component += my
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
def test_ansc_raises_if_subcomponent_changed(root):
    c2 = Component()
    root.component += c2
    c2.changed = True
    with pytest.raises(batou.UpdateNeeded):
        root.component.assert_no_subcomponent_changes()


def test_ansc_does_not_raise_if_no_subcomponent_changed(root):
    c2 = Component()
    root.component += c2
    c2.changed = False
    root.component.assert_no_subcomponent_changes()


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
    c = Component()
    os.utime(reference, (0, 0))
    c.touch(reference)
    assert os.stat(reference).st_mtime != 0
    with open(reference, 'r') as r:
        assert 'Hello world' == r.read()


def test_expand(root):
    assert root.component.expand('Hello {{host.fqdn}}') == (
        'Hello host')


def test_templates(root):
    with open('sample', 'w') as template:
        template.write('Hello {{host.fqdn}}')
    assert root.component.template('sample') == (
        'Hello host\n')


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


def test_root_and_component_know_working_dir(root):
    assert root.workdir.endswith('/work/mycomponent')
    assert root.component.workdir.endswith('/work/mycomponent')


def test_root_component_repr():
    host = Mock()
    root = RootComponent('haproxy', object, host, [])
    assert repr(root).startswith('<RootComponent "haproxy" object at ')


def test_component_manages_working_dir(root):
    previous_workdir = os.getcwd()
    os.rmdir(root.workdir)

    class RememberWorkDir(Component):
        def verify(self):
            self.parent.i_was_in = os.getcwd()
    root.component += RememberWorkDir()
    root.component.deploy()
    assert os.path.isdir(root.workdir)
    assert (os.path.realpath(root.component.i_was_in) ==
            os.path.realpath(root.workdir))
    cwd = os.getcwd()
    # Need to ensure we resolve symlinks: on OS x /var/tmp may lead to
    # /private/...
    assert os.path.realpath(cwd) == os.path.realpath(previous_workdir)


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
