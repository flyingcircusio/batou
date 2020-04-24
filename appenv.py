#!/usr/bin/env python3
# appenv - a single file 'application in venv bootstrapping and updating
#          mechanism for python-based (CLI) applications

# Assumptions:
#
#	- the appenv file is placed in a repo with the name of the application
#   - the name of the application/file is an entrypoint XXX
#   - python3.X+ with ensurepip
#   - a requirements.txt file next to the appenv file

# TODO
#
# - provide a `clone` meta command to create a new project based on this one
#   maybe use an entry point to allow further initialisation of the clone.


import argparse
import glob
import hashlib
import os
import os.path
import shlex
import shutil
import subprocess
import sys
import venv


def cmd(c, quiet=False):
    # TODO revisit the cmd() architecture w/ python 3
    # XXX better IO management for interactive output and seeing original errors
    # and output at appropriate places ...
    try:
        return subprocess.check_output([c], stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError as e:
        if not quiet:
            print("{} returned with exit code {}".format(c, e.returncode))
            print(e.output.decode('ascii'))
        raise


def ensure_venv(target):
    if os.path.exists(os.path.join(target, 'bin', 'pip3')):
        # XXX Support probing the target whether it works properly and rebuild
        # if necessary
        return

    if os.path.exists(target):
        cmd('rm -rf {target}'.format(target=target))

    try:
        # This is trying to detect whether we're on a proper Python stdlib
        # or on a fucked up debian. See various StackOverflow questions about
        # this.
        import distutils.util
        import ensurepip
    except ModuleNotFoundError:
        # Ok, lets unfuck this, if we can. May need privilege escalation 
        # at some point.
        cmd('apt-get -y -q install python3-distutils python3-venv')
    venv.create(target, with_pip=True)


def update_lockfile(argv, meta_args):
    print('Updating lockfile')
    tmpdir = os.path.join(meta_args.appenvdir, 'updatelock')
    ensure_venv(tmpdir)
    print('Installing packages ...')
    cmd('{tmpdir}/bin/pip3 install -r requirements.txt'.format(tmpdir=tmpdir))
    result = cmd('{tmpdir}/bin/pip3 freeze'.format(tmpdir=tmpdir))
    with open('requirements.lock', 'wb') as f:
        f.write(result)
    cmd('rm -rf {tmpdir}'.format(tmpdir=tmpdir))


def _prepare(meta_args):
    # copy used requirements.txt into the target directory so we can use that
    # to check later
    # - when to clean up old versions? keep like one or two old revisions?
    # - enumerate the revisions and just copy the requirements.txt, check
    #   for ones that are clean or rebuild if necessary

    if meta_args.unclean:
        print('Running unclean installation from requirements.txt')
        env_dir = os.path.join(meta_args.appenvdir, 'unclean')
        ensure_venv(env_dir)
        print("Ensuring unclean install ...")
        cmd('{env_dir}/bin/pip3 install -r requirements.txt --upgrade'.format(env_dir=env_dir))
    else:
        requirements = open('requirements.lock', 'rb').read()
        env_hash = hashlib.new('sha256', requirements).hexdigest()
        env_dir = os.path.join(meta_args.appenvdir, env_hash)

        whitelist = set([env_dir, os.path.join(meta_args.appenvdir, 'unclean')])
        for path in glob.glob('{meta_args.appenvdir}/*'.format(meta_args=meta_args)):
            if not path in whitelist:
                print('Removing expired path: {path} ...'.format(path=path))
                if not os.path.isdir(path):
                    os.unlink(path)
                else:
                    shutil.rmtree(path)
        if os.path.exists(env_dir):
            # check whether the existing environment is OK, it might be nice
            # to rebuild in a separate place if necessary to avoid interruptions
            # to running services, but that isn't what we're using it for at the
            # moment
            try:
                if not os.path.exists('{env_dir}/appenv.ready'.format(env_dir=env_dir)):
                    raise Exception()
            except Exception:
                print('Existing envdir not consistent, deleting')
                cmd('rm -rf {env_dir}'.format(env_dir=env_dir))

        if not os.path.exists(env_dir):
            ensure_venv(env_dir)

            with open(os.path.join(env_dir, 'requirements.lock'), 'wb') as f:
                f.write(requirements)

            print('Installing {meta_args.appname} ...'.format(meta_args=meta_args))
            cmd('{env_dir}/bin/pip3 install --no-deps -r {env_dir}/requirements.lock'.format(env_dir=env_dir))

            cmd('{env_dir}/bin/pip3 check'.format(env_dir=env_dir))

            with open(os.path.join(env_dir, 'appenv.ready'), 'w') as f:
                f.write('Ready or not, here I come, you can\'t hide\n')

    return env_dir


def run(argv, meta_args):
    env_dir = _prepare(meta_args)
    os.execv(os.path.join(env_dir, 'bin', meta_args.appname), argv)


def python(argv, meta_args):
    env_dir = _prepare(meta_args)
    interpreter = os.path.join(env_dir, 'bin', 'python')
    argv[0] = interpreter
    os.execv(interpreter, argv)


def reset(argv, meta_args):
    print('Resetting ALL application environments in {appenvdir} ...'.format(appenvdir=meta_args.appenvdir))
    cmd('rm -rf {appenvdir}'.format(format(appenvdir=meta_args.appenvdir)))


def main():
    base = os.path.abspath(os.path.dirname(__file__))
    os.chdir(base)

    # Allow called programs to find out where the wrapper lives
    os.environ['APPENV_BASEDIR'] = base

    if not os.path.exists('requirements.txt'):
        print('Missing `requirements.txt` - this is not a proper appenv '
              ' directory.')
        sys.exit(1)

    # clear PYTHONPATH variable to get a defined environment
    # XXX this is a bit of history. not sure whether its still needed. keeping it
    # for good measure
    if 'PYTHONPATH' in os.environ:
        del os.environ['PYTHONPATH']

    # Prepare args for us and args for the actual target program.
    meta_argv = []
    argv = []

    # Preprocess sys.arv
    for arg in sys.argv:
        if 'appenv-' in arg:
            meta_argv.append(arg.replace('appenv-', ''))
        else:
            argv.append(arg)

    if not os.path.exists('requirements.lock'):
        print('WARNING: no lock file found, implicitly running unclean build')
        meta_argv.append('-u')

    default_appname = os.path.splitext(os.path.basename(__file__))[0]

    # Parse the appenv arguments
    meta_parser = argparse.ArgumentParser()
    meta_parser.add_argument(
        '-u', '--unclean', action='store_true',
        help='Use an unclean working environment.')

    meta_parser.add_argument(
        '--appname', default=default_appname)
    meta_parser.add_argument(
        '--appenvdir', default='.'+default_appname)
    meta_parser.set_defaults(func=run)

    subparsers = meta_parser.add_subparsers()
    p = subparsers.add_parser(
        'update-lockfile', help='Update the lock file.')
    p.set_defaults(func=update_lockfile)

    p = subparsers.add_parser(
        'reset', help='Reset the environment.')
    p.set_defaults(func=reset)

    p = subparsers.add_parser(
        'python', help='Spawn the embedded Python interpreter REPL')
    p.set_defaults(func=python)

    meta_args = meta_parser.parse_args(meta_argv)

    if not os.path.exists(meta_args.appenvdir):
        os.makedirs(meta_args.appenvdir)

    meta_args.func(argv, meta_args)


if __name__ == '__main__':
    main()
