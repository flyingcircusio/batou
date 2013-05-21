from __future__ import print_function, unicode_literals
from batou.component import Component, RootComponent, platform
from batou.tests import TestCase
import batou
from mock import Mock, patch
import os
import os.path
import shutil
import tempfile
import time


class TestComponent(Component):
    updated = False
    needs_update = True

    def verify(self):
        if self.needs_update:
            raise batou.UpdateNeeded()

    def update(self):
        self.updated = True


class ComponentTests(TestCase):

    def test_init_with_no_arguments_creates_plain_component(self):
        component = Component()
        # Lazy initialized attribute
        self.assertFalse(hasattr(component, 'sub_components'))

    def test_plain_component_runs_noop_configure_verify_update(self):
        component = Component()
        component.configure()
        component.verify()
        component.update()

    def test_init_component_with_namevar_uses_first_argument(self):
        class TestComponent(Component):
            namevar = 'asdf'
        component = TestComponent('foobar')
        self.assertEquals('foobar', component.asdf)

    def test_init_component_with_namevar_fails_without_argument(self):
        class TestComponent(Component):
            namevar = 'asdf'
        with self.assertRaises(ValueError):
            TestComponent()

    def test_init_keyword_args_update_dict(self):
        component = Component(foobar=1)
        self.assertEquals(1, component.foobar)

    def test_remote_bootstrap(self):
        # The default remote bootstrap doesn't do anything: just exercise that
        # it's there.  This could go away once we start testing the remoting
        # code.
        component = Component(Mock())
        component.remote_bootstrap(Mock())

    def test_prepare_sets_up_vars(self):
        service = Mock()
        environment = Mock()
        host = Mock()
        root = Mock()
        parent = Mock()
        component = Component()
        component.prepare(
            service, environment, host, root, parent)
        self.assertEquals(service, component.service)
        self.assertEquals(environment, component.environment)
        self.assertEquals(host, component.host)
        self.assertEquals(root, component.root)
        self.assertEquals(parent, component.parent)

    def test_prepare_calls_configure(self):
        component = Component()
        component.configure = Mock()
        component.prepare(None, Mock(), None, None)
        self.assertTrue(component.configure.called)

    def test_prepare_configures_applicable_platforms_as_subcomponents(self):
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
        self.assertEquals(1, len(component.sub_components))
        self.assertIsInstance(component.sub_components[0], MyPlatform)
        # Because we currently have no defined behaviour about this
        # I'm playing this rather safe: a sub-class of a component does not
        # automatically get to have the same platform components applied.
        other_component = MyOtherComponent()
        other_component.prepare(None, environment, None, None)
        self.assertEquals(0, len(other_component.sub_components))

    def test_deploy_empty_component_runs_without_error(self):
        component = Component()
        component.prepare(None, Mock(), None, None)
        component.deploy()

    def test_deploy_update_performed_if_needed(self):
        component = TestComponent(needs_update=True)
        component.prepare(None, Mock(), None, None)
        component.deploy()
        self.assertTrue(component.updated)

    def test_deploy_update_not_performed_if_not_needed(self):
        component = TestComponent(needs_update=False)
        component.prepare(None, Mock(), None, None)
        component.deploy()
        self.assertFalse(component.updated)

    def test_sub_components_are_deployed_first(self):
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
        self.assertEquals(
            [u'2:verify', u'2:update', u'1:verify', u'1:update'], log)

    def test_adding_subcomponents_configures_them_immediately(self):
        class MyComponent(Component):
            configured = False

            def configure(self):
                self.configured = True
        component = Component()
        component.prepare(None, Mock(), None, None)
        my = MyComponent()
        component += my
        self.assertTrue(my.configured)

    # AFIC = assert file is current
    def test_afic_raises_if_nonexisting_file(self):
        component = Component()
        with self.assertRaises(batou.UpdateNeeded):
            component.assert_file_is_current('idonotexist')

    def test_afic_doesnt_raise_if_file_exists_but_no_reference_is_given(self):
        component = Component()
        component.assert_file_is_current(__file__)

    def test_afic_raises_if_file_isolder_than_reference(self):
        fd, reference = tempfile.mkstemp()
        self.addCleanup(os.unlink, reference)
        component = Component()
        with self.assertRaises(batou.UpdateNeeded):
            component.assert_file_is_current(__file__, [reference])

    # ANSC = assert no subcomponent changes
    def test_ansc_raises_if_subcomponent_changed(self):
        c = Component()
        c.prepare(None, Mock(), 'localhost', None)
        c2 = Component()
        c += c2
        c2.changed = True
        with self.assertRaises(batou.UpdateNeeded):
            c.assert_no_subcomponent_changes()

    def test_ansc_does_not_raise_if_no_subcomponent_changed(self):
        c = Component()
        c.prepare(None, Mock(), 'localhost', None)
        c2 = Component()
        c += c2
        c2.changed = False
        c.assert_no_subcomponent_changes()

    def test_cmd_returns_output(self):
        c = Component()
        self.assertEquals(('1\n', ''), c.cmd('echo 1'))

    @patch('sys.stdout')
    def test_cmd_raises_if_error(self, stdout):
        c = Component()
        with self.assertRaises(RuntimeError):
            c.cmd('non-existing-command')

    def test_cmd_returns_output_if_ignore_returncode(self):
        c = Component()
        out, err = c.cmd('echo important output && false', silent=True,
                         ignore_returncode=True)
        self.assertEquals('important output\n', out)

    def test_touch_creates_new_file(self):
        reference = tempfile.mktemp()
        self.assertFalse(os.path.exists(reference))
        c = Component()
        c.touch(reference)
        self.assertTrue(os.path.exists(reference))
        self.addCleanup(os.unlink, reference)

    def test_touch_updates_mtime_leaves_content_intact(self):
        fd, reference = tempfile.mkstemp()
        self.addCleanup(os.unlink, reference)
        with open(reference, 'w') as r:
            r.write('Hello world')
        mtime = os.stat(reference).st_mtime
        c = Component()
        time.sleep(1)
        c.touch(reference)
        self.assertLess(mtime, os.stat(reference).st_mtime)
        with open(reference, 'r') as r:
            self.assertEqual('Hello world', r.read())

    def test_expand(self):
        c = Component()
        c.prepare(None, Mock(), 'localhost', None)
        self.assertEqual('Hello localhost', c.expand('Hello {{host}}'))

    def test_templates(self):
        sample = tempfile.mktemp()
        with open(sample, 'w') as template:
            template.write('Hello {{host}}')
            self.addCleanup(os.unlink, sample)
        c = Component()
        c.prepare(None, Mock(), 'localhost', None)
        self.assertEqual('Hello localhost\n', c.template(sample))

    def test_chdir_contextmanager_is_stackable(self):
        outer = os.getcwd()
        inner1 = os.path.join(os.path.dirname(__file__), 'fixture')
        inner2 = os.path.join(os.path.dirname(__file__))
        c = Component()
        with c.chdir(inner1):
            self.assertEqual(inner1, os.getcwd())
            with c.chdir(inner2):
                self.assertEqual(inner2, os.getcwd())
            self.assertEqual(inner1, os.getcwd())
        self.assertEqual(outer, os.getcwd())

    def test_root_component_computes_working_dir(self):
        c = Component()
        host = Mock()
        host.environment.workdir_base = 'path-to-service/work'
        root = RootComponent('test', c, c.__class__, host, None)
        c.root = root
        self.assertEquals('path-to-service/work/test', root.workdir)
        self.assertEquals('path-to-service/work/test', c.workdir)

    def test_root_component_creates_working_dir_runs_component_deploy(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        self.addCleanup(os.chdir, os.getcwd())

        class MyComponent(Component):
            pass
        c = MyComponent
        c.deploy = Mock()
        host = Mock()
        host.environment.workdir_base = d + '/work'
        host.environment.overrides = {}
        root = RootComponent('test', c, c.__class__, host, None)
        self.assertFalse(os.path.isdir(root.workdir))
        root.prepare()
        root.deploy()
        self.assertTrue(os.path.isdir(root.workdir))
        cwd = os.getcwd()
        if cwd.startswith('/private/'):
            # On Mac OS X tmpfiles are created in /var/folders/someting *and*
            # /var is symlinked to /private/var. @#$(2#$%)!O
            cwd = cwd.replace('/private/', '/', 1)
        self.assertEquals(root.workdir, cwd)
        self.assertTrue(c.deploy.called)

    @patch('sys.stdout')
    def test_cmd_execution_failed_gives_command_in_exception(self, stdout):
        try:
            c = Component()
            c.cmd('asdf')
        except RuntimeError, e:
            self.assertEquals(
                'Command "asdf" returned unsuccessfully.',
                str(e[0]))
            self.assertEquals(
                127, e[1])

    def test_cmd_should_not_stop_if_process_expects_input(self):
        c = Component()
        stdout, stderr = c.cmd('cat')
        # The assertion is, that the test doesn't freeze.
