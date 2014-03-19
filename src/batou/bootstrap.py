from batou.update import update_bootstrap
from batou.utils import cmd
import logging
import os
import pkg_resources
import re
import sys

logger = logging.getLogger(__name__)


# XXX pkg_resources?
BASE = os.path.dirname(__file__)


def restart(ready):
    if ready:
        os.environ['BATOU_BOOTSTRAPPED'] = '1'
    os.execv('.batou/bin/python',
             ['.batou/bin/python', '-c',
                 'import batou.bootstrap; '
                 'batou.bootstrap.bootstrap()'] + sys.argv)


def bootstrap(activate=True):
    while sys.argv[0] == '-c':
        sys.argv.pop(0)

    if 'BATOU_BOOTSTRAPPED' in os.environ:
        import batou.main
        batou.main.main()
        return

    # Ensure we have the right version of batou
    develop = os.environ['BATOU_DEVELOP']
    if develop and not 'BATOU_DEVELOP_UPDATED' in os.environ:
        cmd('.batou/bin/pip install --no-deps -e {}'.format(develop))
        update_bootstrap(version=os.environ['BATOU_VERSION'],
                         develop=os.environ['BATOU_DEVELOP'])
        os.environ['BATOU_DEVELOP_UPDATED'] = '1'
        restart(False)
    elif not develop:
        expected = os.environ['BATOU_VERSION']
        req = pkg_resources.Requirement.parse('batou=={}'.format(expected))
        try:
            need_update = pkg_resources.working_set.find(req) is None
        except pkg_resources.VersionConflict:
            need_update = True
        if need_update:
            print "Updating to batou=={}".format(expected)
            cmd('.batou/bin/pip install --no-deps batou=={}'.format(expected))
            restart(False)

    # Ensure we have all dependencies
    requirements = open(BASE + '/requirements.txt').readlines()
    if os.path.exists('./requirements.txt'):
        requirements.extend(open('./requirements.txt').readlines())
    for req in requirements:
        req = req.strip()
        if req.startswith('#'):
            continue

        egg = None
        if req.startswith('-e'):
            if '#egg=' in req:
                egg = req.split('#egg=', 1)[-1]
            # icky heuristic to determine it's not a VCS url
            elif '+' not in req:
                # XXX we just *assume* that the local directory has the same
                # name as the egg contained therein
                path = re.split('-e *', req, 1)[1]
                egg = os.path.basename(path)
        else:
            egg = req

        needed = True
        if egg:
            try:
                pkg_resources.require(egg)
            except:
                pass
            else:
                needed = False
        if needed:
            print "Installing {}".format(req)
            cmd('.batou/bin/pip install --egg --no-deps "{}"'.format(req))

    if activate:
        restart(True)
