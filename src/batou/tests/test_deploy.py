import os

import pytest

from batou.tests.ellipsis import Ellipsis


def test_main_with_errors(capsys):
    os.chdir("examples/errors")

    from batou.deploy import main

    with pytest.raises(SystemExit) as r:
        main(
            environment="errors",
            platform=None,
            timeout=None,
            dirty=False,
            consistency_only=False,
            predict_only=False,
            check_and_predict_local=False,
            jobs=None,
            provision_rebuild=False,
        )

    assert r.value.code == 1

    out, err = capsys.readouterr()
    assert err == ""
    # save the output to a file to compare it with the expected output
    assert out == Ellipsis(
        """\
batou/2... (cpython 3...)
================================== Preparing ===================================
📦 main: Loading environment `errors`...
🔍 main: Verifying repository ...
🔑 main: Loading secrets ...

ERROR: Failed loading component file
           File: .../examples/errors/components/component5/component.py
      Exception: invalid syntax (component.py, line 1)
Traceback (simplified, most recent call last):
<no-non-remote-internal-traceback-lines-found>

ERROR: Failed loading component file
           File: .../examples/errors/components/component6/component.py
      Exception: No module named 'asdf'
Traceback (simplified, most recent call last):
  File ".../examples/errors/components/component6/component.py", line 1, in <module>
    import asdf  # noqa: F401 import unused
...
ERROR: Missing component
      Component: missingcomponent

ERROR: Superfluous section in environment configuration
        Section: superfluoussection

ERROR: Override section for unknown component found
      Component: nonexisting-component-section

ERROR: Attribute override found both in environment and secrets
      Component: component1
      Attribute: my_attribute

ERROR: Secrets section for unknown component found
      Component: another-nonexisting-component-section
======================= DEPLOYMENT FAILED (during load) ========================
"""
    )  # noqa: E501 line too long


def test_main_fails_if_no_host_in_environment(capsys):
    os.chdir("examples/errorsnohost")

    from batou.deploy import main

    with pytest.raises(SystemExit) as r:
        main(
            environment="errorsnohost",
            platform=None,
            timeout=None,
            dirty=False,
            consistency_only=False,
            predict_only=False,
            check_and_predict_local=False,
            jobs=None,
            provision_rebuild=False,
        )

    assert r.value.code == 1

    out, err = capsys.readouterr()
    assert err == ""
    assert out == Ellipsis(
        """\
batou/2... (cpython 3...)
================================== Preparing ===================================
📦 main: Loading environment `errorsnohost`...
🔍 main: Verifying repository ...
🔑 main: Loading secrets ...
================== Connecting hosts and configuring model ... ==================

ERROR: No host found in environment.
====================== DEPLOYMENT FAILED (during connect) ======================
"""
    )  # noqa: E501 line too long
