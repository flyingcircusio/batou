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
import re
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
        kwargs = {}
        if isinstance(c, str):
            kwargs["shell"] = True
            c = [c]
        if merge_stderr:
            kwargs["stderr"] = subprocess.STDOUT
        return subprocess.check_output(c, **kwargs)
    except subprocess.CalledProcessError as e:
        print("{} returned with exit code {}".format(c, e.returncode))
        print(e.output.decode("utf-8", "replace"))
        raise ValueError(e.output.decode("utf-8", "replace"))


def python(path, c, **kwargs):
    return cmd([os.path.join(path, "bin/python")] + c, **kwargs)


def pip(path, c, **kwargs):
    return python(path, ["-m", "pip"] + c, **kwargs)


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
        cmd(["rm", "-rf", target])

    version = sys.version.split()[0]
    python_maj_min = ".".join(str(x) for x in sys.version_info[:2])
    print("Creating venv ...")
    venv.create(target, with_pip=False, symlinks=True)

    try:
        # This is trying to detect whether we're on a proper Python stdlib
        # or on a broken Debian. See various StackOverflow questions about
        # this.
        import ensurepip  # noqa: F401 imported but unused
    except ImportError:
        # Okay, lets repair this, if we can. May need privilege escalation
        # at some point.
        # We could do: apt-get -y -q install python3-venv
        # on some systems but it requires root and is specific to Debian.
        # I decided to go a more sledge hammer route.

        # XXX we can speed this up by storing this in ~/.appenv/overlay instead
        # of doing the download for every venv we manage
        print("Activating broken ensurepip stdlib workaround ...")

        tmp_base = tempfile.mkdtemp()
        try:
            download = os.path.join(tmp_base, "download.tar.gz")
            with open(download, mode="wb") as f:
                get(
                    "www.python.org",
                    "/ftp/python/{v}/Python-{v}.tgz".format(v=version),
                    f,
                )

            cmd(["tar", "xf", download, "-C", tmp_base])

            assert os.path.exists(
                os.path.join(tmp_base, "Python-{}".format(version))
            )
            for module in ["ensurepip"]:
                print(module)
                shutil.copytree(
                    os.path.join(
                        tmp_base, "Python-{}".format(version), "Lib", module
                    ),
                    os.path.join(
                        target,
                        "lib",
                        "python{}.{}".format(*sys.version_info[:2]),
                        "site-packages",
                        module,
                    ),
                )

            # (always) prepend the site packages so we can actually have a
            # fixed installation.
            site_packages = os.path.abspath(
                os.path.join(
                    target, "lib", "python" + python_maj_min, "site-packages"
                )
            )
            with open(os.path.join(site_packages, "batou.pth"), "w") as f:
                f.write(
                    "import sys; sys.path.insert(0, '{}')\n".format(
                        site_packages
                    )
                )

        finally:
            shutil.rmtree(tmp_base)

    print("Ensuring pip ...")
    python(target, ["-m", "ensurepip", "--default-pip"])
    pip(target, ["install", "--upgrade", "pip"])


def ensure_minimal_python():
    current_python = os.path.realpath(sys.executable)
    preferences = None
    if os.path.exists("requirements.txt"):
        with open("requirements.txt") as f:
            for line in f:
                # Expected format:
                # # appenv-python-preference: 3.1,3.9,3.4
                if not line.startswith("# appenv-python-preference: "):
                    continue
                preferences = line.split(":")[1]
                preferences = [x.strip() for x in preferences.split(",")]
                preferences = list(filter(None, preferences))
                break
    if not preferences:
        # We have no preferences defined, use the current python.
        print("Update lockfile with with {}.".format(current_python))
        print("If you want to use a different version, set it via")
        print(" `# appenv-python-preference:` in requirements.txt.")
        return

    preferences.sort(key=lambda s: [int(u) for u in s.split(".")])

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
            subprocess.check_call(
                [python, "-c", "print(1)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue

        argv = [os.path.basename(python)] + sys.argv
        os.environ["APPENV_BEST_PYTHON"] = python
        os.execv(python, argv)
    else:
        print("Could not find the minimal preferred Python version.")
        print("To ensure a working requirements.lock on all Python versions")
        print("make Python {} available on this system.".format(preferences[0]))
        sys.exit(66)


def ensure_best_python(base):
    os.chdir(base)

    if "APPENV_BEST_PYTHON" in os.environ:
        # Don't do this twice to avoid being surprised with
        # accidental infinite loops.
        return
    import shutil

    # use newest Python available if nothing else is requested
    preferences = ["3.{}".format(x) for x in reversed(range(4, 20))]

    if os.path.exists("requirements.txt"):
        with open("requirements.txt") as f:
            for line in f:
                # Expected format:
                # # appenv-python-preference: 3.1,3.9,3.4
                if not line.startswith("# appenv-python-preference: "):
                    continue
                preferences = line.split(":")[1]
                preferences = [x.strip() for x in preferences.split(",")]
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
            subprocess.check_call(
                [python, "-c", "print(1)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            continue
        argv = [os.path.basename(python)] + sys.argv
        os.environ["APPENV_BEST_PYTHON"] = python
        os.execv(python, argv)
    else:
        print("Could not find a preferred Python version.")
        print("Preferences: {}".format(", ".join(preferences)))
        sys.exit(65)


class ParsedRequirement:
    """A parsed requirement from a requirement string.

    Has a similiar interface to the real Requirement class from
    packaging.requirements, but is reduced to the parts we need.
    """

    def __init__(self, name, url, requirement_string):
        self.name = name
        self.url = url
        self.requirement_string = requirement_string

    def __str__(self):
        return self.requirement_string


def parse_requirement_string(requirement_string):
    """Parse a requirement from a requirement string.

    This function is a simplified version of the Requirement class from
    packaging.requirements.
    Previously, this was done using pkg_resources.parse_requirements,
    but pkg_resources is deprecated and errors out on import.
    And the replacement packaging is apparently not packaged in python
    virtualenvs where we need it.

    See packaging / _parser.py for the requirements grammar.
    As well as packaging / _tokenizer.py for the tokenization rules/regexes.
    """
    # packaging / _tokenizer.py
    identifier_regex = r"\b[a-zA-Z0-9][a-zA-Z0-9._-]*\b"
    url_regex = r"[^ \t]+"
    whitespace_regex = r"[ \t]+"
    # comments copied from packaging / _parser.py
    # requirement = WS? IDENTIFIER WS? extras WS? requirement_details
    # extras = (LEFT_BRACKET wsp* extras_list? wsp* RIGHT_BRACKET)?
    # requirement_details = AT URL (WS requirement_marker?)?
    #                     | specifier WS? (requirement_marker)?
    # requirement_marker = SEMICOLON marker WS?
    # consider these comments for illustrative purporses only, since according
    # to the source code, the actual grammar is subtly different from this :)

    # We will make some simplifications here:
    # - We only care about the name, and URL if present.
    # - We assume that the requirement string is well-formed. If not,
    #   pip operations will fail later on.
    # - We will not parse extras, specifiers, or markers.

    # check for name
    name_match = re.search(
        f"^(?:{whitespace_regex})?{identifier_regex}", requirement_string
    )
    name = name_match.group() if name_match else None
    # check for URL
    url_match = re.search(
        f"@(?:{whitespace_regex})?(?P<url>{url_regex})"
        f"(?:{whitespace_regex})?;?",
        requirement_string,
    )
    url = url_match.group("url") if url_match else None

    return ParsedRequirement(name, url, requirement_string)


class AppEnv(object):

    base = None  # The directory where we add the environments. Co-located
    # with the application script - not necessarily the appenv
    # script so we can link to an appenv script from multiple
    # locations.

    env_dir = None  # The current specific venv that we're working with.
    appenv_dir = None  # The directory where to place specific venvs.

    def __init__(self, base, original_cwd):
        self.base = base

        # This used to be computed based on the application name but
        # as we can have multiple application names now, we always put the
        # environments into '.appenv'. They're hashed anyway.
        self.appenv_dir = os.path.join(self.base, ".appenv")

        # Allow simplifying a lot of code by assuming that all the
        # meta-operations happen in the base directory. Store the original
        # working directory here so we switch back at the appropriate time.
        self.original_cwd = original_cwd

    def meta(self):
        # Parse the appenv arguments
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        p = subparsers.add_parser(
            "update-lockfile", help="Update the lock file."
        )
        p.set_defaults(func=self.update_lockfile)

        p = subparsers.add_parser("init", help="Create a new appenv project.")
        p.set_defaults(func=self.init)

        p = subparsers.add_parser("reset", help="Reset the environment.")
        p.set_defaults(func=self.reset)

        p = subparsers.add_parser("prepare", help="Prepare the venv.")
        p.set_defaults(func=self.prepare)

        p = subparsers.add_parser(
            "python", help="Spawn the embedded Python interpreter REPL"
        )
        p.set_defaults(func=self.python)

        p = subparsers.add_parser(
            "run",
            help="Run a script from the bin/ directory of the virtual env.",
        )
        p.add_argument("script", help="Name of the script to run.")
        p.set_defaults(func=self.run_script)

        args, remaining = parser.parse_known_args()

        if not hasattr(args, "func"):
            parser.print_usage()
        else:
            args.func(args, remaining)

    def run(self, command, argv):
        self.prepare()
        cmd = os.path.join(self.env_dir, "bin", command)
        argv = [cmd] + argv
        os.environ["APPENV_BASEDIR"] = self.base
        os.chdir(self.original_cwd)
        os.execv(cmd, argv)

    def _assert_requirements_lock(self):
        if not os.path.exists("requirements.lock"):
            print(
                "No requirements.lock found. Generate it using"
                " ./appenv update-lockfile"
            )
            sys.exit(67)

        with open("requirements.lock") as f:
            locked_hash = None
            for line in f:
                if line.startswith("# appenv-requirements-hash: "):
                    locked_hash = line.split(":")[1].strip()
                    break
            if locked_hash != self._hash_requirements():
                print(
                    "requirements.txt seems out of date (hash mismatch). "
                    "Regenerate using ./appenv update-lockfile"
                )
                sys.exit(67)

    def _hash_requirements(self):
        with open("requirements.txt", "rb") as f:
            hash_content = f.read()
        return hashlib.new("sha256", hash_content).hexdigest()

    def prepare(self, args=None, remaining=None):
        # copy used requirements.txt into the target directory so we can use
        # that to check later
        # - when to clean up old versions? keep like one or two old revisions?
        # - enumerate the revisions and just copy the requirements.txt, check
        #   for ones that are clean or rebuild if necessary
        os.chdir(self.base)

        self._assert_requirements_lock()

        hash_content = []
        with open("requirements.lock", "rb") as f:
            requirements = f.read()
        hash_content.append(os.fsencode(os.path.realpath(sys.executable)))
        hash_content.append(requirements)
        with open(__file__, "rb") as f:
            hash_content.append(f.read())
        env_hash = hashlib.new("sha256", b"".join(hash_content)).hexdigest()[:8]
        env_dir = os.path.join(self.appenv_dir, env_hash)

        whitelist = set(
            [
                env_dir,
                os.path.join(self.appenv_dir, "unclean"),
                os.path.join(self.appenv_dir, "current"),
            ]
        )
        for path in glob.glob(
            "{appenv_dir}/*".format(appenv_dir=self.appenv_dir)
        ):
            if path not in whitelist:
                print("Removing expired path: {path} ...".format(path=path))
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
                    "{env_dir}/appenv.ready".format(env_dir=env_dir)
                ):
                    raise Exception()
            except Exception:
                print("Existing envdir not consistent, deleting")
                cmd(["rm", "-rf", env_dir])

        if not os.path.exists(env_dir):
            ensure_venv(env_dir)

            with open(os.path.join(env_dir, "requirements.lock"), "wb") as f:
                f.write(requirements)

            print("Installing ...")
            pip(
                env_dir,
                [
                    "install",
                    "--no-deps",
                    "-r",
                    "{env_dir}/requirements.lock".format(env_dir=env_dir),
                ],
            )
            pip(env_dir, ["check"])

            with open(os.path.join(env_dir, "appenv.ready"), "w") as f:
                f.write("Ready or not, here I come, you can't hide\n")
            current_path = os.path.join(self.appenv_dir, "current")
            try:
                os.unlink(current_path)
            except FileNotFoundError:
                pass
            os.symlink(env_hash, current_path)

        self.env_dir = env_dir

    def init(self, args=None, remaining=None):
        print("Let's create a new appenv project.\n")
        command = None
        while not command:
            command = input("What should the command be named? ").strip()
        dependency = input(
            "What is the main dependency as found on PyPI? [{}] ".format(
                command
            )
        ).strip()
        if not dependency:
            dependency = command
        default_target = os.path.abspath(
            os.path.join(self.original_cwd, command)
        )
        target = input(
            "Where should we create this? [{}] ".format(default_target)
        ).strip()
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
        with open("appenv", "wb") as new_appenv:
            new_appenv.write(bootstrap_data)
        os.chmod("appenv", 0o755)
        if os.path.exists(command):
            os.unlink(command)
        os.symlink("appenv", command)
        with open("requirements.txt", "w") as requirements_txt:
            requirements_txt.write(dependency + "\n")
        print()
        print(
            "Done. You can now `cd {}` and call"
            " `./{}` to bootstrap and run it.".format(
                os.path.relpath(target, self.original_cwd), command
            )
        )

    def python(self, args, remaining):
        self.run("python", remaining)

    def run_script(self, args, remaining):
        self.run(args.script, remaining)

    def reset(self, args=None, remaining=None):
        print(
            "Resetting ALL application environments in {appenvdir} ...".format(
                appenvdir=self.appenv_dir
            )
        )
        cmd(["rm", "-rf", self.appenv_dir])

    def update_lockfile(self, args=None, remaining=None):
        ensure_minimal_python()
        os.chdir(self.base)
        print("Updating lockfile")
        tmpdir = os.path.join(self.appenv_dir, "updatelock")
        if os.path.exists(tmpdir):
            cmd(["rm", "-rf", tmpdir])
        ensure_venv(tmpdir)
        print("Installing packages ...")
        pip(tmpdir, ["install", "-r", "requirements.txt"])

        extra_specs = []
        result = pip(tmpdir, ["freeze", "--all", "--exclude", "pip"]).decode(
            "utf-8"
        )
        # See https://pip.pypa.io/en/stable/cli/pip_freeze/
        # --all
        # Do not skip these packages in the output:
        # setuptools, wheel, distribute, pip
        # --exclude <package>
        # Exclude specified package from the output.
        # We need to include setuptools, since we do a --no-deps install
        # of the requirements.lock file.
        # We are already installing pip in ensure_venv, so we don't need it
        # in the requirements.lock file.
        pinned_versions = {}
        for line in result.splitlines():
            if line.strip().startswith("-e "):
                # We'd like to pick up the original -e statement here.
                continue
            parsed_requirement = parse_requirement_string(line)
            pinned_versions[parsed_requirement.name] = parsed_requirement
        requested_versions = {}
        with open("requirements.txt") as f:
            for line in f.readlines():
                if line.strip().startswith("-e "):
                    extra_specs.append(line.strip())
                    continue
                if line.strip().startswith("--"):
                    extra_specs.append(line.strip())
                    continue

                # filter comments, in particular # appenv-python-preferences
                if line.strip().startswith("#"):
                    continue
                parsed_requirement = parse_requirement_string(line)
                requested_versions[parsed_requirement.name] = parsed_requirement

        final_versions = {}
        for spec in requested_versions.values():
            # Pick versions with URLs to ensure we don't get the screwed up
            # results from pip freeze.
            if spec.url:
                final_versions[spec.name] = spec
        for spec in pinned_versions.values():
            # Ignore versions we already picked
            if spec.name in final_versions:
                continue
            final_versions[spec.name] = spec
        lines = [str(spec) for spec in final_versions.values()]
        lines.extend(extra_specs)
        lines.sort()
        with open(os.path.join(self.base, "requirements.lock"), "w") as f:
            f.write(
                "# appenv-requirements-hash: {}\n".format(
                    self._hash_requirements()
                )
            )
            f.write("\n".join(lines))
            f.write("\n")
        cmd(["rm", "-rf", tmpdir])


def main():
    base = os.path.dirname(__file__)
    original_cwd = os.getcwd()

    ensure_best_python(base)
    # clear PYTHONPATH variable to get a defined environment
    # XXX this is a bit of history. not sure whether its still needed. keeping
    # it for good measure
    if "PYTHONPATH" in os.environ:
        del os.environ["PYTHONPATH"]

    # Determine whether we're being called as appenv or as an application name
    application_name = os.path.splitext(os.path.basename(__file__))[0]

    appenv = AppEnv(base, original_cwd)
    if application_name == "appenv":
        appenv.meta()
    else:
        appenv.run(application_name, sys.argv[1:])


if __name__ == "__main__":
    main()
