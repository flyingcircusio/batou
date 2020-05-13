from batou import ConfigurationError, ConversionError
from batou import MissingOverrideAttributes, DuplicateComponent
from batou import UnknownComponentConfigurationError, UnusedResources
from batou import UnsatisfiedResources, MissingEnvironment
from batou import ComponentLoadingError, MissingComponent, SuperfluousSection
from batou import SuperfluousComponentSection, SuperfluousSecretsSection
from batou import CycleErrorDetected, NonConvergingWorkingSet
from batou import DuplicateHostError, InvalidIPAddressError

from batou.component import ComponentDefinition
import sys


def test_configurationerrors_can_be_sorted(root):
    errors = []
    errors.append(ConfigurationError('asdffdas', root.component))
    errors.append(ConversionError(
        root.component, 'testkey', 'testvalue', str, 'foobar'))
    errors.append(MissingOverrideAttributes(
        root.component, ['asdf', 'bsdfg']))

    errors.append(DuplicateComponent(
        ComponentDefinition(root.component.__class__, 'asdf.py'),
        ComponentDefinition(root.component.__class__, 'bsdf.py')))

    try:
        raise ValueError('asdf')
    except Exception:
        _, exc_value, exc_traceback = sys.exc_info()

    errors.append(UnknownComponentConfigurationError(
        root, exc_value, exc_traceback))

    errors.append(UnusedResources(
        {'asdf': [(root.component, 1)]}))

    errors.append(UnsatisfiedResources(
        {'asdf': [root]}))

    errors.append(MissingEnvironment(root.environment))

    errors.append(ComponentLoadingError('asdf.py', ValueError('asdf')))

    errors.append(MissingComponent('component', 'hostname'))

    errors.append(SuperfluousSection('asdf'))

    errors.append(SuperfluousComponentSection('asdf'))

    errors.append(SuperfluousSecretsSection('asdf'))

    errors.append(CycleErrorDetected('foo'))

    errors.append(NonConvergingWorkingSet([root]))

    errors.append(DuplicateHostError('asdf'))

    errors.append(InvalidIPAddressError(('127.0.0.256/24')))

    errors.sort(key=lambda x: x.sort_key)
