import mock

from batou import NonConvergingWorkingSet, UnsatisfiedResources
from batou.environment import Environment
from batou.resources import Resources


def test_regression_reset_works_if_provided_but_not_required():
    resources = Resources()
    root = mock.Mock()
    resources.provide(root, mock.sentinel.key, "asdf")
    resources.reset_component_resources(root)


def test_reset_marks_depending_components_as_dirty():
    resources = Resources()
    root1 = mock.Mock()
    resources.provide(root1, mock.sentinel.key, "asdf")

    root2 = mock.Mock()
    resources.require(root2, mock.sentinel.key)

    root3 = mock.Mock()
    resources.require(root3, mock.sentinel.key, dirty=True)
    assert resources.dirty_dependencies == set()
    resources.reset_component_resources(root1)
    assert resources.dirty_dependencies == set([root2])


def test_mentions_missing_requirement_with_host_requirement(sample_service):
    e = Environment("test-resources-host")
    e.load()
    errors = e.configure()
    assert len(errors) == 2
    assert isinstance(errors[0], UnsatisfiedResources)
    assert isinstance(errors[1], NonConvergingWorkingSet)
    assert "key" in str(errors[0].__dict__)
