from batou.utils import cmd
import os.path


bootstrap_template = os.path.dirname(__file__) + '/bootstrap-template'


def update_bootstrap(version, develop):
    with open('batou', 'w') as b:
        bootstrap = open(bootstrap_template, 'r').read()
        b.write(bootstrap.format(version=version, develop=develop))


def main(version, develop):
    if finish:
        update_bootstrap(version, develop)
    else:
        if not 'batou' in version:
            # Assume this is a raw version number, not a more complex install spec.
            version = 'batou=={}'.format(version)
        cmd('.batou/bin/pip install --egg {}'.format(version))
        cmd('.batou/bin/batou update \'{}\' \'--develop={}\' --finish'.format(version, develop))
