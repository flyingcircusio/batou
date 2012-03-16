# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.component import Component
from batou.tests import TestCase
import batou
import mock
import os
import os.path
import shutil
import sysconfig
import tempfile


class ComponentTests(TestCase):

    def test_init_with_no_arguments_creates_plain_component(self):
        component = Component()
        self.assertEquals({}, component.hooks)
        self.assertEquals([], component.sub_components)

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
        class MyPlatform(Component):
            platform = 'testplatform'
        class MyOtherPlatform(Component):
            platform = 'other'
        class MyComponent(Component):
            platforms = [MyPlatform, MyOtherPlatform]
        environment = mock.Mock()
        environment.platform = 'testplatform'
        component = MyComponent()
        component.prepare(None, environment, None, None)
        self.assertEquals(1, len(component.sub_components))
        self.assertIsInstance(component.sub_components[0], MyPlatform)

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

