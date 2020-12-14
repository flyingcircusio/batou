from batou.tests.ellipsis import Ellipsis
import os
import pytest


def test_main_with_errors(capsys):
    os.chdir("examples/errors")

    from batou.deploy import main

    with pytest.raises(SystemExit) as r:
        main(
            environment='errors',
            platform=None,
            timeout=None,
            dirty=False,
            consistency_only=False,
            predict_only=False,
            jobs=None)

    assert r.value.code == 1

    out, err = capsys.readouterr()
    assert err == ''
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing ===================================
main: Loading environment `errors`...
main: Verifying repository ...
main: Loading secrets ...

ERROR: Failed loading component file
      File: .../examples/errors/components/component5/component.py
 Exception: invalid syntax (component.py, line 1)

ERROR: Failed loading component file
      File: .../examples/errors/components/component6/component.py
 Exception: No module named 'asdf'

ERROR: Missing component
 Component: missingcomponent
      Host: localhost

ERROR: Superfluous section in environment configuration
   Section: superfluoussection

ERROR: Override section for unknown component found
 Component: nonexisting-component-section

ERROR: Secrets section for unknown component found
 Component: another-nonexisting-component-section
======================= DEPLOYMENT FAILED (during load) ========================
""")
