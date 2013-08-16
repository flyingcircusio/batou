from batou.utils import cmd
import os.path


bootstrap_template = os.path.dirname(__file__) + '/bootstrap-template'


def update_bootstrap(version, develop):
    with open('batou', 'w') as b:
        bootstrap = open(bootstrap_template, 'r').read()
        b.write(bootstrap.format(version=version, develop=develop))


def main(version, develop, finish):
    if finish:
        # This only happens if we're the new batou.
        update_bootstrap(version, develop)
    else:
        if version:
            cmd('.batou/bin/pip install --egg batou=={}'.format(version))
        else:
            cmd('.batou/bin/pip install -e {}'.format(develop))
        cmd('.batou/bin/batou update --version=\'{}\' \'--develop={}\' --finish'.format(version, develop))
