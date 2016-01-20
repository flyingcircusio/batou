from batou import UpdateNeeded, SilentConfigurationError
from batou.component import Component, RootComponent, platform, Attribute
from batou.component import handle_event
from batou.utils import CmdExecutionError
from mock import Mock
import batou
import os
import os.path
import pytest


def MockRoot():
    return Mock(overrides={})


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
    assert root.component.environment is root.environment
    assert root.component.host is root.host
    assert root.component.root is root
    assert root.component.parent is root


def test_op_orassignment_ignores_none(root):
    root.component |= None


def test_recursive_sub_component_iterator(root):
    for x in range(3):
        c = Component(name='x{}'.format(x))
        root.component += c
        for y in range(2):
            c2 = Component(name='x{}y{}'.format(x, y))
            c += c2

    recursive = list(x.name for x in root.component.recursive_sub_components)
    assert (['x0', 'x0y0', 'x0y1',
             'x1', 'x1y0', 'x1y1',
             'x2', 'x2y0', 'x2y1'] == recursive)


def test_op_orassignment_ignores_already_preapred_component(root):
    class Counting(Component):
        x = 1

        def configure(self):
            self.x += 1
    c = Counting()
    root.component |= c
    assert c.x == 2
    root.component |= c
    assert c.x == 2


def test_prepare_calls_configure():
    component = Component()
    component.configure = Mock()
    component.prepare(MockRoot())
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
    component = SampleComponent(needs_update=True)
    root.component += component
    root.component.deploy()
    assert component.updated


def test_deploy_update_not_performed_if_not_needed(root):
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


def test_adding_subcomponents_makes_them_available_as_underscore(root):
    c = Component()
    assert root.component._ is None
    root.component += c
    assert root.component._ is c


def test_oring_subcomponents_makes_them_available_as_underscore(root):
    c = Component()
    assert root.component._ is None
    root.component |= c
    assert root.component._ is c


# AFIC = assert file is current
def test_afic_raises_if_nonexisting_file(root):
    component = Component()
    root.component += component
    with pytest.raises(batou.UpdateNeeded):
        component.assert_file_is_current('idonotexist')


def test_afic_doesnt_raise_if_file_exists_but_no_reference_is_given(root):
    component = Component()
    root.component += component
    component.assert_file_is_current(__file__)


def test_afic_raises_if_file_isolder_than_reference(tmpdir, root):
    component = Component()
    root.component += component
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


# ACIC = assert component is current

def test_acic_raises_if_no_reference(root):
    c = Component()
    c.last_updated = Mock(return_value=None)
    root.component += c
    c2 = Component()
    c2.last_updated = Mock(return_value=21)
    with pytest.raises(batou.UpdateNeeded):
        c.assert_component_is_current(c2)


def test_acic_raises_if_older_reference(root):
    c = Component()
    c.last_updated = Mock(return_value=20)
    root.component += c
    c2 = Component()
    c2.last_updated = Mock(return_value=21)
    with pytest.raises(batou.UpdateNeeded):
        c.assert_component_is_current(c2)


def test_acic_does_not_raise_if_current(root):
    c = Component()
    c.last_updated = Mock(return_value=21)
    root.component += c
    c2 = Component()
    c2.last_updated = Mock(return_value=21)
    c.assert_component_is_current(c2)


def test_acic_does_not_raise_if_newer(root):
    c = Component()
    c.last_updated = Mock(return_value=22)
    root.component += c
    c2 = Component()
    c2.last_updated = Mock(return_value=21)
    c.assert_component_is_current(c2)


def test_acic_accepts_multiple_components(root):
    c = Component()
    c.last_updated = Mock(return_value=20)
    root.component += c
    c2 = Component()
    c2.last_updated = Mock(return_value=21)
    with pytest.raises(batou.UpdateNeeded):
        c.assert_component_is_current([c2, c2])


def test_cmd_expands_jinja():
    c = Component()
    c.foo = 'asdf'
    c.prepare(MockRoot())
    assert ('asdf\n', '') == c.cmd('echo "{{component.foo}}"')


def test_cmd_returns_output():
    c = Component()
    c.prepare(MockRoot())
    assert ('1\n', '') == c.cmd('echo 1')


def test_cmd_raises_if_error():
    c = Component()
    c.prepare(MockRoot())
    with pytest.raises(CmdExecutionError):
        c.cmd('non-existing-command')


def test_cmd_returns_output_if_ignore_returncode():
    c = Component()
    c.prepare(MockRoot())
    out, err = c.cmd('echo important output && false', ignore_returncode=True)
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
            assert inner2 == os.getcwd()  # noqa
        assert inner1 == os.getcwd()
    assert outer == os.getcwd()


def test_root_and_component_know_working_dir(root):
    assert root.workdir.endswith('/work/mycomponent')
    assert root.component.workdir.endswith('/work/mycomponent')


def test_root_component_repr():
    host = Mock()
    environment = Mock()
    root = RootComponent('haproxy', environment, host, [], False,
                         object, '/defdir', '/workdir')
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
    c.prepare(MockRoot())
    with pytest.raises(CmdExecutionError) as e:
        c.cmd('asdf')
    assert e.value.cmd == 'asdf'
    assert e.value.returncode == 127


def test_cmd_should_not_stop_if_process_expects_input():
    c = Component()
    c.prepare(MockRoot())
    stdout, stderr = c.cmd('cat')
    # The assertion is, that the test doesn't get stuck .


def test_last_updated_not_implemented_on_base():
    c = Component()
    with pytest.raises(NotImplementedError):
        c.last_updated()


def test_require_one_convenience_api_returns_scalar():
    c = Component()
    c.require = Mock(return_value=[1])
    assert 1 == c.require_one('asdf')


def test_require_one_convenience_raises_if_no_result():
    c = Component()
    c.require = Mock(return_value=[])
    with pytest.raises(SilentConfigurationError):
        c.require_one('asdf')


def test_require_one_convenience_raises_if_more_results():
    c = Component()
    c.require = Mock(return_value=[1, 2])
    with pytest.raises(KeyError):
        c.require_one('asdf')


def test_assert_cmd_when_succesful():
    c = Component()
    c.prepare(MockRoot())
    c.assert_cmd('true')


def test_assert_cmd_when_unsuccessful():
    c = Component()
    c.prepare(MockRoot())
    with pytest.raises(UpdateNeeded):
        c.assert_cmd('false')


def test_assert_no_changes_local_does_not_raise(root):
    root.component.assert_no_changes()


def test_assert_no_changes_local_raises(root):
    root.component.changed = True
    with pytest.raises(batou.UpdateNeeded):
        root.component.assert_no_changes()


def test_assert_no_changes_recursive_does_not_raise(root):
    root.component += Component()
    root.component.assert_no_changes()


def test_assert_no_changes_recursive_raises(root):
    c2 = Component()
    root.component += c2
    c2.changed = True
    with pytest.raises(batou.UpdateNeeded):
        root.component.assert_no_changes()


def test_root_overrides_missing_attribute_raises(root):
    root.overrides = {'asdf': 1}
    with pytest.raises(batou.MissingOverrideAttributes) as e:
        root.prepare()
    assert e.value.attributes == ['asdf']


def test_root_overrides_existing_attribute(root):
    root.factory.asdf = None
    root.overrides = {'asdf': 1}
    root.prepare()
    assert root.component.asdf == 1


def test_attribute_split_list(root):
    class Foo(Component):
        a = Attribute('list', '')
        b = Attribute('list', '1,2')
        c = Attribute('list', '3')
        d = Attribute('list', '  3, 3,')
        e = Attribute('list', [])
    f = Foo()
    root.component += f
    root.prepare()
    assert f.a == []
    assert f.b == ['1', '2']
    assert f.c == ['3']
    assert f.d == ['3', '3']
    assert f.e == []


class EventHandlingComponent(Component):

    namevar = 'x'
    perform_update = True

    def verify(self):
        if self.perform_update:
            raise UpdateNeeded()

    def configure(self):
        self.log = []

    @handle_event('before-update', '*')
    def handle(self, component):
        self.log.append(component.x)


def test_event_handler_before_update_no_changes(root):
    c = EventHandlingComponent('1', perform_update=False)
    root.component += c
    root.component.deploy()
    assert c.log == []


def test_event_handler_before_update_with_changes_all(root):
    c1 = EventHandlingComponent('1')
    c2 = EventHandlingComponent('2')
    root.component += c1
    root.component += c2
    root.component.deploy()
    assert c1.log == ['1', '2']
    assert c2.log == ['1', '2']


def test_event_handler_before_update_with_changes_precursor(root):
    from batou.component import handle_event
    log = []

    class Foo(Component):
        namevar = 'x'

        def verify(self):
            raise UpdateNeeded()

        @handle_event('before-update', 'precursor')
        def handle(self, component):
            log.append((self.x, component.x))
    root.component += Foo('1')
    root.component += Foo('2')
    root.component.deploy()
    assert log == [('2', '1')]
