from batou.resources import Resources
import mock


def test_regression_reset_works_if_provided_but_not_required():
    resources = Resources()
    root = mock.Mock()
    resources.provide(root, mock.sentinel.key, 'asdf')
    resources.reset_component_resources(root)


def test_reset_marks_depending_components_as_dirty():
    resources = Resources()
    root1 = mock.Mock()
    resources.provide(
        root1, mock.sentinel.key, 'asdf')

    root2 = mock.Mock()
    resources.require(
        root2, mock.sentinel.key)

    root3 = mock.Mock()
    resources.require(
        root3, mock.sentinel.key, dirty=True)
    assert resources.dirty_dependencies == set()
    resources.reset_component_resources(root1)
    assert resources.dirty_dependencies == set([root2])
