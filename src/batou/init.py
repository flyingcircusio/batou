from batou.update import update_bootstrap
from batou.utils import cmd
from batou import output
import argparse
import os.path
import pkg_resources
import shutil


def main(destination):
    develop = os.environ['BATOU_DEVELOP']
    if develop:
        output.warn(
            'Initializing with a development copy of batou will cause your '
            'project to have a reference outside its repository. '
            'Use at your own risk. ')
        develop = os.path.abspath(develop)
    print('Bootstrapping new batou project in {}. This can take a while.'
          .format(os.path.abspath(destination)))
    if os.path.exists(destination):
        print('{} exists already. Not copying template structure.'.format(
              destination))
        os.chdir(destination)
    else:
        source = os.path.dirname(__file__) + '/init-template'
        shutil.copytree(source, destination)
        os.chdir(destination)
        cmd('hg -y init .')
    update_bootstrap(os.environ['BATOU_VERSION'], develop)
    # Need to clean up to avoid inheriting info that we're bootstrapped
    # already.
    for key in list(os.environ):
        if key.startswith('BATOU_'):
            del os.environ[key]
    cmd('./batou --help')


def console_main():
    parser = argparse.ArgumentParser(
        description="""\
Initialize batou project in the given directory. If the given directory does
not exist, it will be created.

If no directory is given, the current directory is used.
""")
    parser.add_argument('destination')

    os.environ['BATOU_VERSION'] = pkg_resources.require('batou')[0].version
    os.environ['BATOU_DEVELOP'] = ''
    args = parser.parse_args()
    main(args.destination)
