import os
import os.path
import shutil

from batou.environment import Environment
from batou.tests.ellipsis import Ellipsis
from batou.utils import cmd


def test_service_early_resource():
    env = Environment(
        "dev",
        basedir=os.path.dirname(__file__) + "/fixture/service_early_resource")
    env.load()
    env.configure()
    assert env.resources.get("zeo") == ["127.0.0.1:9000"]


def test_example_errors_early():
    os.chdir("examples/errors")
    out, _ = cmd("./batou deploy errors", acceptable_returncodes=[1])
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

ERROR: Failed loading component file
      File: .../examples/errors/components/component7/component.py
 Exception: Attributes only support one of those parameters: either `default` or `default_conf_string`.

ERROR: Missing component
 Component: component7
      Host: localhost

ERROR: Missing component
 Component: missingcomponent
      Host: localhost

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
""")  # noqa: E501 line too long


def test_example_errors_gpg_cannot_decrypt(monkeypatch):
    monkeypatch.setitem(os.environ, "GNUPGHOME", '')
    os.chdir("examples/errors")
    out, _ = cmd("./batou deploy errors", acceptable_returncodes=[1])
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing ===================================
main: Loading environment `errors`...
main: Verifying repository ...
main: Loading secrets ...

ERROR: Error while calling GPG
   command: gpg --decrypt secrets/errors.cfg
 exit code: 2
   message:
gpg: ...
...
ERROR: Failed loading component file
      File: .../examples/errors/components/component5/component.py
 Exception: invalid syntax (component.py, line 1)

ERROR: Failed loading component file
      File: .../examples/errors/components/component6/component.py
 Exception: No module named 'asdf'

ERROR: Failed loading component file
      File: .../examples/errors/components/component7/component.py
 Exception: Attributes only support one of those parameters: either `default` or `default_conf_string`.

ERROR: Missing component
 Component: component7
      Host: localhost

ERROR: Missing component
 Component: missingcomponent
      Host: localhost

ERROR: Superfluous section in environment configuration
   Section: superfluoussection

ERROR: Override section for unknown component found
 Component: nonexisting-component-section
======================= DEPLOYMENT FAILED (during load) ========================
""")  # noqa: E501 line too long


def test_example_errors_late():
    os.chdir("examples/errors2")
    out, _ = cmd("./batou deploy errors", acceptable_returncodes=[1])

    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing ===================================
main: Loading environment `errors`...
main: Verifying repository ...
main: Loading secrets ...
================================ Connecting ... ================================
localhost: Connecting via local (1/1)
============================ Configuring model ... =============================

ERROR: Trying to access address family IPv6 which is not configured for localhost:22.
      Hint: Use `require_v6=True` when instantiating the Address object.

ERROR: crontab@localhost: No cron jobs found.

ERROR: Failed override attribute conversion
      Host: localhost
 Attribute: Component1.do_what_is_needed
Conversion: convert_literal('false')
     Error: malformed node or string: <...Name object at 0x...>

ERROR: Failed override attribute conversion
      Host: localhost
 Attribute: DNSProblem.attribute_with_problem
Conversion: Address('localhost')
     Error: Need port for service address.

ERROR: Failed override attribute conversion
      Host: localhost
 Attribute: FileMode > File('work/filemode/new-file.txt') > Mode('new-file.txt').mode
Conversion: convert_mode('wrongmode')
     Error: Mode-string should be between `---------` and `rwxrwxrwx`.

ERROR: Overrides for undefined attributes
      Host: localhost
 Component: Component2
Attributes: this_does_not_exist, this_also_does_not_exist

ERROR: Unused provided resources
    Resource "backend" provided by component3 with value ['192.168.0.1']
    Resource "frontend" provided by component3 with value ['test00.gocept.net']
    Resource "sub" provided by component3 with value [<SubComponent (localhost) "Component3 > SubComponent('sub sub')">]

ERROR: Unsatisfied resource requirements
    Resource "application" required by component4

ERROR: Found dependency cycle
cycle1 depends on
        cycle2
cycle2 depends on
        cycle1

ERROR: 8 remaining unconfigured component(s)
======================= 10 ERRORS - CONFIGURATION FAILED =======================
===================== DEPLOYMENT FAILED (during configure) =====================
""")  # noqa: E501 line too long


def test_example_errors_missing_environment():
    os.chdir("examples/errors")
    out, _ = cmd("./batou deploy production", acceptable_returncodes=[1])
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing ===================================
main: Loading environment `production`...

ERROR: Missing environment
Environment: production
======================= DEPLOYMENT FAILED (during load) ========================
""")  # noqa: E501 line too long


def test_example_ignores():
    os.chdir("examples/ignores")
    out, _ = cmd("./batou deploy ignores")
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing ===================================
main: Loading environment `ignores`...
main: Verifying repository ...
main: Loading secrets ...
================================ Connecting ... ================================
localhost: Connecting via local (1/2)
otherhost: Connection ignored (2/2)
============================ Configuring model ... =============================
==================== Waiting for remaining connections ... =====================
================================== Deploying ===================================
localhost: Scheduling component component1 ...
localhost: Skipping component fail ... (Component ignored)
otherhost: Skipping component fail2 ... (Host ignored)
=================================== Summary ====================================
============================= DEPLOYMENT FINISHED ==============================
""")  # noqa: E501 line too long


def test_example_async_sync_deployment():
    os.chdir("examples/sync_async")
    out, _ = cmd("./batou -d deploy default")
    print(out)
    assert "Number of jobs: 1" in out

    out, _ = cmd("./batou -d deploy -j 2 default")
    print(out)
    assert "Number of jobs: 2" in out

    out, _ = cmd("./batou -d deploy async")
    print(out)
    assert "Number of jobs: 2" in out


def test_example_job_option_overrides_environment():
    os.chdir("examples/sync_async")
    out, _ = cmd("./batou -d deploy -j 5 async")
    print(out)
    assert "Number of jobs: 5" in out


def test_consistency_does_not_start_deployment():
    os.chdir("examples/tutorial-helloworld")
    out, _ = cmd("./batou deploy -c tutorial")
    print(out)
    assert "Deploying" not in out
    assert "localhost: Scheduling" not in out
    assert "CONSISTENCY CHECK FINISHED" in out

    # Counter-test that "Deploying" and "localhost: Scheduling" show
    # up if deployments happen
    out, _ = cmd("./batou deploy tutorial")
    print(out)
    assert "Deploying" in out
    assert "localhost: Scheduling" in out
    assert "CONSISTENCY CHECK FINISHED" not in out


def test_diff_is_not_shown_for_keys_in_secrets(tmp_path, monkeypatch, capsys):
    """It does not render diffs for files which contain secrets.

    Secrets might be in the config file in secrets/ or additional encrypted
    files belonging to the environment.
    """
    monkeypatch.chdir('examples/tutorial-secrets')
    if os.path.exists('work'):
        shutil.rmtree('work')
    try:
        out, _ = cmd("./batou deploy tutorial")
    finally:
        shutil.rmtree('work')
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing ===================================
main: Loading environment `tutorial`...
main: Verifying repository ...
main: Loading secrets ...
================================ Connecting ... ================================
localhost: Connecting via local (1/1)
============================ Configuring model ... =============================
==================== Waiting for remaining connections ... =====================
================================== Deploying ===================================
localhost: Scheduling component hello ...
localhost > Hello > File('work/hello/hello') > Presence('hello')
localhost > Hello > File('work/hello/hello') > Content('hello')
Not showing diff as it contains sensitive data,
see ...diff for the diff.
localhost > Hello > File('work/hello/other-secrets.yaml') > Presence('other-secrets.yaml')
localhost > Hello > File('work/hello/other-secrets.yaml') > Content('other-secrets.yaml')
Not showing diff as it contains sensitive data,
see ...diff for the diff.
=================================== Summary ====================================
============================= DEPLOYMENT FINISHED ==============================
""")  # noqa: E501 line too long
