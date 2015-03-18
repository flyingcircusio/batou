from batou.utils import cmd
import batou.template
import os.path


bootstrap_template = os.path.dirname(__file__) + '/bootstrap-template'


def update_bootstrap(version, develop):
    engine = batou.template.Jinja2Engine()
    template = open(bootstrap_template, 'r').read()
    bootstrap = engine.expand(template, dict(version=version, develop=develop))

    with open('batou', 'w') as b:
        b.write(bootstrap)


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
