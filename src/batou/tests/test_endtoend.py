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
batou/... (CPython 2.7...)
================================== Preparing =================================\
==
main: Loading environment `errors`...
main: Verifying repository ...
main: Loading secrets ...
================================== Connecting ================================\
==
localhost: Connecting via local (1/1)
ERROR: Failed loading component file
           File: .../examples/errors/components/component5/component.py
      Exception: invalid syntax (component.py, line 1)
ERROR: Failed loading component file
           File: .../examples/errors/components/component6/component.py
      Exception: No module named asdf
ERROR: Missing component
      Component: missingcomponent
           Host: localhost
ERROR: Superfluous section in environment configuration
        Section: superfluoussection
ERROR: Override section for unknown component found
      Component: nonexisting-component-section
ERROR: Overrides for undefined attributes
           Host: localhost
      Component: Component2
     Attributes: this_does_not_exist
ERROR: Failed override attribute conversion
           Host: localhost
      Attribute: Component1.do_what_is_needed
     Conversion: convert_literal(u'false')
          Error: malformed string
ERROR: Found dependency cycle
     cycle1 depends on
             cycle2
     cycle2 depends on
             cycle1
ERROR: Unsatisfied resource requirements
     application: <undefined>
ERROR: 4 remaining unconfigured component(s)
ERROR: Unused provided resources
       frontend: ['test00.gocept.net']
        backend: ['192.168.0.1']
======================= 11 ERRORS - CONFIGURATION FAILED =====================\
==
============================== DEPLOYMENT FAILED =============================\
==
""")
