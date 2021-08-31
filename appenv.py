#!/usr/bin/env python3
# appenv - a single file 'application in venv bootstrapping and updating
#          mechanism for python-based (CLI) applications

# Assumptions:
#
#   - the appenv file is placed in a repo with the name of the application
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
import http.client
import os
import os.path
import shutil
import subprocess
import sys
import tempfile
import venv


def cmd(c, merge_stderr=True, quiet=False):
    # TODO revisit the cmd() architecture w/ python 3
    # XXX better IO management for interactive output and seeing original
    # errors and output at appropriate places ...
    try:
        kwargs = {"shell": True}
        if merge_stderr:
            kwargs["stderr"] = subprocess.STDOUT
        return subprocess.check_output([c], **kwargs)
    except subprocess.CalledProcessError as e:
        print("{} returned with exit code {}".format(c, e.returncode))
        print(e.output.decode("ascii"))
        raise ValueError(e.output.decode("ascii"))


def get(host, path, f):
    conn = http.client.HTTPSConnection(host)
    conn.request("GET", path)
    r1 = conn.getresponse()
    assert r1.status == 200, (r1.status, host, path, r1.read()[:100])
    chunk = r1.read(16 * 1024)
    while chunk:
        f.write(chunk)
        chunk = r1.read(16 * 1024)
    conn.close()


def ensure_venv(target):
    if os.path.exists(os.path.join(target, "bin", "pip3")):
        # XXX Support probing the target whether it works properly and rebuild
        # if necessary
        return

    if os.path.exists(target):
        print("Deleting unclean target)")
        cmd("rm -rf {target}".format(target=target))

    version = sys.version.split()[0]
    python_maj_min = ".".join(str(x) for x in sys.version_info[:2])
    print("Creating venv ...")
    venv.create(target, with_pip=False)

    try:
        # This is trying to detect whether we're on a proper Python stdlib
        # or on a broken Debian. See various StackOverflow questions about
        # this.
        import distutils.util  # noqa: F401 imported but unused
        import ensurepip  # noqa: F401 imported but unused
    except ImportError:
        # Okay, lets repair this, if we can. May need privilege escalation
        # at some point.
        # We could do: apt-get -y -q install python3-distutils python3-venv
        # on some systems but it requires root and is specific to Debian.
        # I decided to go a more sledge hammer route.

        # XXX we can speed this up by storing this in ~/.appenv/overlay instead
        # of doing the download for every venv we manage
        print("Activating broken distutils/ensurepip stdlib workaround ...")

        tmp_base = tempfile.mkdtemp()
        try:
            download = os.path.join(tmp_base, "download.tar.gz")
            with open(download, mode="wb") as f:
                get("www.python.org",
                    "/ftp/python/{v}/Python-{v}.tgz".format(v=version), f)

            cmd("tar xf {} -C {}".format(download, tmp_base))

            assert os.path.exists(
                os.path.join(tmp_base, "Python-{}".format(version)))
            for module in ["ensurepip", "distutils"]:
                print(module)
                shutil.copytree(
                    os.path.join(tmp_base, "Python-{}".format(version), "Lib",
                                 module),
                    os.path.join(target, "lib",
                                 "python{}.{}".format(*sys.version_info[:2]),
                                 "site-packages", module))

            # (always) prepend the site packages so we can actually have a
            # fixed distutils installation.
            site_packages = os.path.abspath(
                os.path.join(target, "lib", "python" + python_maj_min,
                             "site-packages"))
            with open(os.path.join(site_packages, "batou.pth"), "w") as f:
                f.write("import sys; sys.path.insert(0, '{}')\n".format(
                    site_packages))

        finally:
            shutil.rmtree(tmp_base)

    print("Ensuring pip ...")
    cmd("{target}/bin/python -m ensurepip --default-pip".format(target=target))
    cmd("{target}/bin/python -m pip install --upgrade pip".format(
        target=target))


def ensure_minimal_python():
    current_python = os.path.realpath(sys.executable)
    preferences = None
    if os.path.exists('requirements.txt'):
        with open('requirements.txt') as f:
            for line in f:
                # Expected format:
                # # appenv-python-preference: 3.1,3.9,3.4
                if not line.startswith("# appenv-python-preference: "):
                    continue
                preferences = line.split(':')[1]
                preferences = [x.strip() for x in preferences.split(',')]
                preferences = list(filter(None, preferences))
                break
    if not preferences:
        # We have no preferences defined, use the current python.
        print("Update lockfile with with {}.".format(current_python))
        print("If you want to use a different version, set it as via")
        print(" `# appenv-python-preference:` in requirements.txt.")
        return

    preferences.sort(key=lambda s: [int(u) for u in s.split('.')])

    for version in preferences[0:1]:
        python = shutil.which("python{}".format(version))
        if not python:
            # not a usable python
            continue
        python = os.path.realpath(python)
        if python == current_python:
            # found a preferred python and we're already running as it
            break
        # Try whether this Python works
        try:
            subprocess.check_call([python, "-c", "print(1)"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue

        argv = [os.path.basename(python)] + sys.argv
        os.environ["APPENV_BEST_PYTHON"] = python
        os.execv(python, argv)
    else:
        print("Could not find the minimal preferred Python version.")
        print("To ensure a working requirements.lock on all Python versions")
        print("make Python {} available on this system.".format(
            preferences[0]))
        sys.exit(66)


def ensure_best_python(base):
    os.chdir(base)

    if "APPENV_BEST_PYTHON" in os.environ:
        # Don't do this twice to avoid being surprised with
        # accidental infinite loops.
        return
    import shutil

    # use newest Python available if nothing else is requested
    preferences = ['3.{}'.format(x) for x in reversed(range(4, 20))]

    if os.path.exists('requirements.txt'):
        with open('requirements.txt') as f:
            for line in f:
                # Expected format:
                # # appenv-python-preference: 3.1,3.9,3.4
                if not line.startswith("# appenv-python-preference: "):
                    continue
                preferences = line.split(':')[1]
                preferences = [x.strip() for x in preferences.split(',')]
                preferences = list(filter(None, preferences))
                break

    current_python = os.path.realpath(sys.executable)
    for version in preferences:
        python = shutil.which("python{}".format(version))
        if not python:
            # not a usable python
            continue
        python = os.path.realpath(python)
        if python == current_python:
            # found a preferred python and we're already running as it
            break
        # Try whether this Python works
        try:
            subprocess.check_call([python, "-c", "print(1)"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        argv = [os.path.basename(python)] + sys.argv
        os.environ["APPENV_BEST_PYTHON"] = python
        os.execv(python, argv)
    else:
        print("Could not find a preferred Python version.")
        print("Preferences: {}".format(', '.join(preferences)))
        sys.exit(65)


class AppEnv(object):

    base = None  # The directory where we add the environments. Co-located
    # with the application script - not necessarily the appenv
    # script so we can link to an appenv script from multiple
    # locations.

    env_dir = None  # The current specific venv that we're working with.
    appenv_dir = None  # The directory where to place specific venvs.

    def __init__(self, base):
        self.base = base

        # This used to be computed based on the application name but
        # as we can have multiple application names now, we always put the
        # environments into '.appenv'. They're hashed anyway.
        self.appenv_dir = os.path.join(self.base, '.appenv')

        # Allow simplifying a lot of code by assuming that all the
        # meta-operations happen in the base directory. Store the original
        # working directory here so we switch back at the appropriate time.
        self.original_cwd = os.path.abspath(os.curdir)

    def meta(self):
        # Parse the appenv arguments
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        p = subparsers.add_parser(
            "update-lockfile", help="Update the lock file.")
        p.set_defaults(func=self.update_lockfile)

        p = subparsers.add_parser("init", help="Create a new appenv project.")
        p.set_defaults(func=self.init)

        p = subparsers.add_parser("reset", help="Reset the environment.")
        p.set_defaults(func=self.reset)

        p = subparsers.add_parser(
            "python", help="Spawn the embedded Python interpreter REPL")
        p.set_defaults(func=self.python)

        p = subparsers.add_parser(
            "run",
            help="Run a script from the bin/ directory of the virtual env.")
        p.add_argument("script", help="Name of the script to run.")
        p.set_defaults(func=self.run_script)

        args, remaining = parser.parse_known_args()

        if not hasattr(args, 'func'):
            parser.print_usage()
        else:
            args.func(args, remaining)

    def run(self, command, argv):
        self._prepare()
        cmd = os.path.join(self.env_dir, 'bin', command)
        argv = [cmd] + argv
        os.environ['APPENV_BASEDIR'] = self.base
        os.chdir(self.original_cwd)
        os.execv(cmd, argv)

    def _prepare(self):
        # copy used requirements.txt into the target directory so we can use
        # that to check later
        # - when to clean up old versions? keep like one or two old revisions?
        # - enumerate the revisions and just copy the requirements.txt, check
        #   for ones that are clean or rebuild if necessary
        os.chdir(self.base)
        if not os.path.exists('requirements.lock'):
            print('Running unclean installation from requirements.txt')
            env_dir = os.path.join(self.appenv_dir, 'unclean')
            ensure_venv(env_dir)
            print('Ensuring unclean install ...')
            cmd('{env_dir}/bin/python -m pip install -r requirements.txt'
                ' --upgrade'.format(env_dir=env_dir))
        else:
            hash_content = []
            requirements = open("requirements.lock", "rb").read()
            hash_content.append(os.fsencode(os.path.realpath(sys.executable)))
            hash_content.append(requirements)
            hash_content.append(open(__file__, "rb").read())
            env_hash = hashlib.new("sha256",
                                   b"".join(hash_content)).hexdigest()[:8]
            env_dir = os.path.join(self.appenv_dir, env_hash)

            whitelist = set([
                env_dir, os.path.join(self.appenv_dir, "unclean")])
            for path in glob.glob(
                    "{appenv_dir}/*".format(appenv_dir=self.appenv_dir)):
                if path not in whitelist:
                    print(
                        "Removing expired path: {path} ...".format(path=path))
                    if not os.path.isdir(path):
                        os.unlink(path)
                    else:
                        shutil.rmtree(path)
            if os.path.exists(env_dir):
                # check whether the existing environment is OK, it might be
                # nice to rebuild in a separate place if necessary to avoid
                # interruptions to running services, but that isn't what we're
                # using it for at the  moment
                try:
                    if not os.path.exists(
                            "{env_dir}/appenv.ready".format(env_dir=env_dir)):
                        raise Exception()
                except Exception:
                    print("Existing envdir not consistent, deleting")
                    cmd("rm -rf {env_dir}".format(env_dir=env_dir))

            if not os.path.exists(env_dir):
                ensure_venv(env_dir)

                with open(os.path.join(env_dir, "requirements.lock"),
                          "wb") as f:
                    f.write(requirements)

                print("Installing ...")
                cmd("{env_dir}/bin/python -m pip install --no-deps -r"
                    " {env_dir}/requirements.lock".format(env_dir=env_dir))

                cmd("{env_dir}/bin/python -m pip check".format(
                    env_dir=env_dir))

                with open(os.path.join(env_dir, "appenv.ready"), "w") as f:
                    f.write("Ready or not, here I come, you can't hide\n")

        self.env_dir = env_dir

    def init(self, args=None, remaining=None):
        print("Let's create a new appenv project.\n")
        command = None
        while not command:
            command = input("What should the command be named? ").strip()
        dependency = input(
            "What is the main dependency as found on PyPI? [{}] ".format(
                command)).strip()
        if not dependency:
            dependency = command
        default_target = os.path.abspath(
            os.path.join(self.original_cwd, command))
        target = input("Where should we create this? [{}] ".format(
            default_target)).strip()
        if target:
            target = os.path.join(self.original_cwd, target)
        else:
            target = default_target
        target = os.path.abspath(target)
        if not os.path.exists(target):
            os.makedirs(target)
        print()
        print("Creating appenv setup in {} ...".format(target))
        with open(__file__, "rb") as bootstrap_file:
            bootstrap_data = bootstrap_file.read()
        os.chdir(target)
        with open('appenv', "wb") as new_appenv:
            new_appenv.write(bootstrap_data)
        os.chmod('appenv', 0o755)
        if os.path.exists(command):
            os.unlink(command)
        os.symlink('appenv', command)
        with open("requirements.txt", "w") as requirements_txt:
            requirements_txt.write(dependency + "\n")
        print()
        print("Done. You can now `cd {}` and call"
              " `./{}` to bootstrap and run it.".format(
                  os.path.relpath(target, self.original_cwd), command))

    def python(self, args, remaining):
        self.run('python', remaining)

    def run_script(self, args, remaining):
        self.run(args.script, remaining)

    def reset(self, args=None, remaining=None):
        print(
            "Resetting ALL application environments in {appenvdir} ...".format(
                appenvdir=self.appenv_dir))
        cmd("rm -rf {appenvdir}".format(appenvdir=self.appenv_dir))

    def update_lockfile(self, args=None, remaining=None):
        ensure_minimal_python()
        os.chdir(self.base)
        print("Updating lockfile")
        tmpdir = os.path.join(self.appenv_dir, "updatelock")
        if os.path.exists(tmpdir):
            cmd("rm -rf {tmpdir}".format(tmpdir=tmpdir))
        ensure_venv(tmpdir)
        print("Installing packages ...")
        cmd("{tmpdir}/bin/python -m pip install -r requirements.txt".format(
            tmpdir=tmpdir))

        # Hack because we might not have pkg_resources, but the venv should
        tmp_paths = cmd(
            "{tmpdir}/bin/python -c"
            " 'import sys; print(\"\\n\".join(sys.path))'".format(
                tmpdir=tmpdir),
            merge_stderr=False).decode(sys.getfilesystemencoding())
        for line in tmp_paths.splitlines():
            line = line.strip()
            if not line:
                continue
            sys.path.append(line)
        import pkg_resources

        extra_specs = []
        result = cmd(
            "{tmpdir}/bin/python -m pip freeze".format(tmpdir=tmpdir),
            merge_stderr=False).decode('ascii')
        pinned_versions = {}
        for line in result.splitlines():
            if line.strip().startswith('-e '):
                # We'd like to pick up the original -e statement here.
                continue
            spec = list(pkg_resources.parse_requirements(line))[0]
            pinned_versions[spec.project_name] = spec
        requested_versions = {}
        with open('requirements.txt') as f:
            for line in f.readlines():
                if line.strip().startswith('-e '):
                    extra_specs.append(line.strip())
                    continue
                # filter comments, in particular # appenv-python-preferences
                if line.strip().startswith('#'):
                    continue
                spec = list(pkg_resources.parse_requirements(line))[0]
                requested_versions[spec.project_name] = spec

        final_versions = {}
        for spec in requested_versions.values():
            # Pick versions with URLs to ensure we don't get the screwed up
            # results from pip freeze.
            if spec.url:
                final_versions[spec.project_name] = spec
        for spec in pinned_versions.values():
            # Ignore versions we already picked
            if spec.project_name in final_versions:
                continue
            final_versions[spec.project_name] = spec
        lines = [str(spec) for spec in final_versions.values()]
        lines.extend(extra_specs)
        lines.sort()
        with open(os.path.join(self.base, "requirements.lock"), "w") as f:
            f.write('\n'.join(lines))
            f.write('\n')
        cmd("rm -rf {tmpdir}".format(tmpdir=tmpdir))


def main():
    base = os.path.dirname(__file__)

    ensure_best_python(base)
    # clear PYTHONPATH variable to get a defined environment
    # XXX this is a bit of history. not sure whether its still needed. keeping
    # it for good measure
    if "PYTHONPATH" in os.environ:
        del os.environ["PYTHONPATH"]

    # Determine whether we're being called as appenv or as an application name
    application_name = os.path.splitext(os.path.basename(__file__))[0]

    appenv = AppEnv(base)
    try:
        if application_name == 'appenv':
            appenv.meta()
        else:
            appenv.run(application_name, sys.argv[1:])
    finally:
        os.chdir(appenv.original_cwd)


if __name__ == "__main__":
    main()
