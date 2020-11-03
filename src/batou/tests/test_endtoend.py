from batou.environment import Environment
from batou.utils import cmd
import os
import os.path
from batou.tests.ellipsis import Ellipsis


def test_service_early_resource():
    env = Environment(
        'dev',
        basedir=os.path.dirname(__file__) + '/fixture/service_early_resource')
    env.load()
    env.configure()
    assert env.resources.get('zeo') == ['127.0.0.1:9000']


def test_example_errors():
    os.chdir('examples/errors')
    out, _ = cmd('./batou deploy errors', acceptable_returncodes=[1])
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing =================================\
==
main: Loading environment `errors`...
main: Verifying repository ...
main: Loading secrets ...
================================ Connecting ... ==============================\
==
localhost: Connecting via local (1/1)
============================ Configuring model ... ===========================\
==
ERROR: Failed loading component file
      File: .../component5/component.py
 Exception: invalid syntax (component.py, line 1)
ERROR: Failed loading component file
      File: .../component6/component.py
 Exception: No module named 'asdf'
ERROR: Missing component
 Component: missingcomponent
      Host: localhost
ERROR: Superfluous section in environment configuration
   Section: superfluoussection
ERROR: Override section for unknown component found
 Component: nonexisting-component-section
ERROR: crontab@localhost: No cron jobs found.
ERROR: Failed override attribute conversion
      Host: localhost
 Attribute: Component1.do_what_is_needed
Conversion: convert_literal('false')
     Error: malformed node or string: ...ast.Name object at 0x...>
ERROR: Failed override attribute conversion
      Host: localhost
 Attribute: DNSProblem.attribute_with_problem
Conversion: Address('localhost')
     Error: Need port for service address.
ERROR: Overrides for undefined attributes
      Host: localhost
 Component: Component2
Attributes: this_does_not_exist
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
ERROR: 6 remaining unconfigured component(s)
======================= 13 ERRORS - CONFIGURATION FAILED =====================\
==
============================== DEPLOYMENT FAILED =============================\
==
""")  # NOQA


def test_example_errors_missing_environment():
    os.chdir('examples/errors')
    out, _ = cmd('./batou deploy production', acceptable_returncodes=[1])
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing =================================\
==
main: Loading environment `production`...
ERROR: Missing environment
Environment: production
============================== DEPLOYMENT FAILED =============================\
==
""")  # NOQA


def test_example_ignores():
    os.chdir('examples/ignores')
    out, _ = cmd('./batou deploy ignores')
    assert out == Ellipsis("""\
batou/2... (cpython 3...)
================================== Preparing =================================\
==
main: Loading environment `ignores`...
main: Verifying repository ...
main: Loading secrets ...
================================ Connecting ... ==============================\
==
localhost: Connecting via local (1/2)
otherhost: Connection ignored (2/2)
============================ Configuring model ... ===========================\
==
==================== Waiting for remaining connections ... ===================\
==
================================== Deploying =================================\
==
localhost: Scheduling component component1 ...
localhost: Skipping component fail ... (Component ignored)
otherhost: Skipping component fail2 ... (Host ignored)
============================= DEPLOYMENT FINISHED ============================\
==
""")


def test_example_async_sync_deployment():
    os.chdir('examples/sync_async')
    out, _ = cmd('./batou -d deploy default')
    print(out)
    assert "Number of jobs: 1" in out

    out, _ = cmd('./batou -d deploy -j 2 default')
    print(out)
    assert "Number of jobs: 2" in out

    out, _ = cmd('./batou -d deploy async')
    print(out)
    assert "Number of jobs: 2" in out


def test_example_job_option_overrides_environment():
    os.chdir('examples/sync_async')
    out, _ = cmd('./batou -d deploy -j 5 async')
    print(out)
    assert "Number of jobs: 5" in out
