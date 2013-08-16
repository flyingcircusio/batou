from batou.update import update_bootstrap
from batou.utils import cmd
import os
import pkg_resources
import sys
import logging

logger = logging.getLogger(__name__)


def bootstrap():
    restart = False
    # Assume that we've been started from a maybe-too-old environment that is
    # barely working.
    # This code doesn't get checked into individual projects and can thus be
    # more elaborate on fixing the environment as soon as we got it running.
    batou_pkg = pkg_resources.require('batou')[0]
    develop = os.environ['BATOU_DEVELOP']
    if develop:
        # In development mode the code for generating the bootstrap file might
        # change without anyone calling ./batou update, so we rather update it
        # automatically.
        update_bootstrap(version=os.environ['BATOU_VERSION'],
                         develop=os.environ['BATOU_DEVELOP'])
        if not os.path.samefile(develop+'/src', batou_pkg.location):
            print "Updating to development version in {}".format(develop)
            cmd('.batou/bin/pip install -e {}'.format(develop))
            restart = True
    else:
        expected = os.environ['BATOU_VERSION']
        current = batou_pkg.version
        if current != expected:
            print "Updating to batou=={}".format(expected)
            cmd('.batou/bin/pip install batou=={}'.format(expected))
            restart = True

    if restart:
        print "Restarting after upgrade ..."
        os.execv('.batou/bin/batou', sys.argv)
