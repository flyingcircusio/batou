from batou.utils import cmd
import os.path


bootstrap_template = os.path.dirname(__file__) + '/bootstrap-template'


def update_bootstrap(version, develop):
    with open('batou', 'w') as b:
        bootstrap = open(bootstrap_template, 'r').read()
        b.write(bootstrap.format(version=version, develop=develop))


def main(version, develop, finish):
    # Record that we're updating. This will be called twice: first when the
    # user asks for updating, which ensures that any subsequent calls won't
    # downgrade in the first bootstrap phase. Second, we call the newly
    # installed batou with '--finish' to update the early bootstrapping file
    # itself.
    update_bootstrap(version, develop)
    if finish:
        return
    if version:
        cmd('.batou/bin/pip install --egg batou=={}'.format(version))
    else:
        cmd('.batou/bin/pip install --egg -e {}'.format(develop))
    cmd('./batou update --version=\'{}\' '
        '\'--develop={}\' --finish'.format(version, develop))
