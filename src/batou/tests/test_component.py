# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.component import Component, RootComponent, platform
from batou.tests import TestCase
import batou
import mock
import os
import os.path
import shutil
import subprocess
import sysconfig
import tempfile
import time


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
            component = TestComponent()

    def test_init_keyword_args_update_dict(self):
        component = Component(foobar=1)
        self.assertEquals(1, component.foobar)

    def test_prepare_sets_up_vars(self):
        service = mock.Mock()
        environment = mock.Mock()
        host = mock.Mock()
        root = mock.Mock()
        parent = mock.Mock()
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
        component.configure = mock.Mock()
        component.prepare(None, None, None, None)
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
        environment = mock.Mock()
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
        component.deploy()

    def test_deploy_update_performed_if_needed(self):
        class MyComponent(Component):
            updated = False
            def verify(self):
                raise batou.UpdateNeeded()
            def update(self):
                self.updated = True
        component = MyComponent()
        component.prepare(None, None, None, None)
        component.deploy()
        self.assertTrue(component.updated)

    def test_deploy_update_not_performed_if_not_needed(self):
        class MyComponent(Component):
            updated = False
            def verify(self):
                pass
            def update(self):
                self.updated = True
        component = MyComponent()
        component.prepare(None, None, None, None)
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
        top.prepare(None, None, None, None)
        top += MyComponent('2')
        top.deploy()
        self.assertEquals(
            [u'2:verify', u'2:update', u'1:verify', u'1:update'], log)

    def test_adding_subcomponents_prepares_them_immediately(self):
        class MyComponent(Component):
            prepared = False
            def configure(self):
                self.prepared = True
        component = Component()
        component.prepare(None, None, None, None)
        my = MyComponent()
        component += my
        self.assertTrue(my.prepared)

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

    def test_cmd_returns_output(self):
        c = Component()
        self.assertEquals(('1\n', ''), c.cmd('echo 1'))

    @mock.patch('sys.stdout')
    def test_cmd_raises_if_error(self, stdout):
        c = Component()
        with self.assertRaises(RuntimeError):
            c.cmd('non-existing-command')

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
        c.prepare(None, None, 'localhost', None)
        self.assertEqual('Hello localhost', c.expand('Hello {{host}}'))

    def test_templates(self):
        sample = tempfile.mktemp()
        with open(sample, 'w') as template:
            template.write('Hello {{host}}')
            self.addCleanup(os.unlink, sample)
        c = Component()
        c.prepare(None, None, 'localhost', None)
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
        c.service = mock.Mock()
        c.service.base = 'path-to-service'
        root = RootComponent('test', c, None, None)
        self.assertEquals('path-to-service/work/test', root.workdir)

    def test_root_component_creates_working_dir_runs_component_deploy(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        self.addCleanup(os.chdir, os.getcwd())
        c = Component()
        c.deploy = mock.Mock()
        c.service = mock.Mock()
        c.service.base = d
        root = RootComponent('test', c, None, None)
        self.assertFalse(os.path.isdir(root.workdir))
        root.deploy()
        self.assertTrue(os.path.isdir(root.workdir))
        cwd = os.getcwd()
        if cwd.startswith('/private/'):
            # On Mac OS X tmpfiles care created in /var/folders/someting *and*
            # /var is symlinked to /private/var. @#$(2#$%)!O
            cwd = cwd.replace('/private/', '/', 1)
        self.assertEquals(root.workdir, cwd)
        self.assertTrue(c.deploy.called)

    @mock.patch('sys.stdout')
    def test_cmd_execution_failed_gives_command_in_exception(self, stdout):
        try:
            c = Component()
            c.cmd('asdf')
        except RuntimeError, e:
            self.assertEquals('Command "asdf" returned unsuccessfully.', str(e))

    def test_cmd_should_not_stop_if_process_expects_input(self):
        c = Component()
        stdout, stderr = c.cmd('cat')
        # The assertion is, that the test doesn't freeze.
