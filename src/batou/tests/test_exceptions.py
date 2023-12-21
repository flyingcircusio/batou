import sys

from batou import (
    ComponentLoadingError,
    ConfigurationError,
    ConversionError,
    CycleErrorDetected,
    DuplicateComponent,
    DuplicateHostError,
    InvalidIPAddressError,
    MissingComponent,
    MissingEnvironment,
    MissingOverrideAttributes,
    NonConvergingWorkingSet,
    SuperfluousComponentSection,
    SuperfluousSecretsSection,
    SuperfluousSection,
    UnknownComponentConfigurationError,
    UnsatisfiedResources,
    UnusedResources,
)
from batou.component import ComponentDefinition


def test_configurationerrors_can_be_sorted(root):
    errors = []
    errors.append(ConfigurationError.from_context("asdffdas", root.component))
    errors.append(
        ConversionError.from_context(
            root.component, "testkey", "testvalue", str, "foobar"
        )
    )
    errors.append(
        MissingOverrideAttributes.from_context(
            root.component, ["asdf", "bsdfg"]
        )
    )

    errors.append(
        DuplicateComponent.from_context(
            ComponentDefinition(root.component.__class__, "asdf.py"),
            ComponentDefinition(root.component.__class__, "bsdf.py"),
        )
    )

    try:
        raise ValueError("asdf")
    except Exception:
        _, exc_value, exc_traceback = sys.exc_info()

    errors.append(
        UnknownComponentConfigurationError.from_context(
            root, exc_value, exc_traceback
        )
    )

    errors.append(UnusedResources.from_context({"asdf": {root: 1}}))

    errors.append(UnsatisfiedResources.from_context({"asdf": [root]}))

    errors.append(MissingEnvironment.from_context(root.environment))

    errors.append(
        ComponentLoadingError.from_context("asdf.py", ValueError("asdf"), None)
    )

    errors.append(MissingComponent.from_context("component", "hostname"))

    errors.append(SuperfluousSection.from_context("asdf"))

    errors.append(SuperfluousComponentSection.from_context("asdf"))

    errors.append(SuperfluousSecretsSection.from_context("asdf"))

    errors.append(CycleErrorDetected.from_context("foo"))

    errors.append(NonConvergingWorkingSet.from_context([root]))

    errors.append(DuplicateHostError.from_context("asdf"))

    errors.append(InvalidIPAddressError.from_context(("127.0.0.256/24")))

    errors.sort(key=lambda x: x.sort_key)
