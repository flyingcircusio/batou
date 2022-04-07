"""Summarize status of secret files."""

import pathlib
import sys

from batou import GPGCallError

from .encryption import EncryptedConfigFile


class UnknownEnvironmentError(ValueError):
    """There is/are no environment(s) for this name(s)."""

    def __init__(self, names: list):
        self.names = names

    def __str__(self):
        return f'Unknown environment(s): {", ".join(self.names)}'


class Environment(object):
    def __init__(self, path: pathlib.Path = None, name=None):
        if path:
            self.path = path
            self.name = path.parent.name
        else:
            self.name = name
            self.path = pathlib.Path("environments" / name / "secrets.cfg")

        self.f = EncryptedConfigFile(
            self.path, add_files_for_env=self.name, write_lock=True, quiet=True
        )
        self.f.__enter__()

    def __del__(self):
        try:
            self.f.__exit__()
        except AttributeError:
            pass

    @classmethod
    def all(cls):
        for path in pathlib.Path("environments").glob("*/environment.cfg"):
            path = path.parent / "secrets.cfg"
            yield Environment(path=path)

    @classmethod
    def by_filter(cls, filter):
        if filter:
            filter = filter.split(",")
        environments = []
        for e in cls.all():
            if filter:
                if e.name in filter:
                    filter.remove(e.name)
                else:
                    continue
            environments.append(e)
        if filter:
            raise UnknownEnvironmentError(filter)
        return environments

    def summary(self):
        try:
            self.f.read()
        except Exception as e:
            print("\t{}".format(e))
            return
        print("\t members")
        members = self.f.config.get("batou", "members")
        for m in members.value.split(","):
            m = m.strip()
            print("\t\t-", m)
        if not members:
            print("\t\t(none)")
        print("\t secret files")
        # Keys of self.f.files are strings, but self.path is pathlib.Path:
        files = [f for f in self.f.files if f != str(self.path)]
        files = [
            f.replace("secrets/{}-".format(self.name), "", 1) for f in files
        ]
        for f in files:
            print("\t\t-", f)
        if not files:
            print("\t\t(none)")
        print()

    def add_user(self, keyid):
        try:
            self.f.read()
        except Exception as e:
            print("\t{}".format(e))
            return
        members = self.f.get_members()
        if keyid not in members:
            members.append(keyid)
            self.f.set_members(members)
            try:
                self.f.write()
            except Exception as e:
                print("\t{}".format(e))
                return
        self.summary()

    def remove_user(self, keyid):
        try:
            self.f.read()
        except Exception as e:
            print("\t{}".format(e))
            return
        members = self.f.get_members()
        if keyid in members:
            members.remove(keyid)
            self.f.set_members(members)
            try:
                self.f.write()
            except Exception as e:
                print("\t{}".format(e))
                return
        self.summary()


def summary(**kw):
    """Secrets editor console script.

    The main focus here is to avoid having unencrypted files accidentally
    ending up in the deployment repository.

    """
    try:
        for e in Environment.all():
            print(e.name)
            e.summary()
    except GPGCallError as e:
        print(e, file=sys.stderr)
        print(e.output, file=sys.stderr)
        return 1  # exit code


def add_user(keyid, environments, **kw):
    """Add a user to a given environment.

    If environments is not given, a user is added
    to all environments.

    """
    for e in Environment.by_filter(environments):
        print(e.name)
        e.add_user(keyid)
        print()


def remove_user(keyid, environments, **kw):
    """Remove a user from a given environment.

    If environments is not given, the user is removed
    from all environments.

    """
    for e in Environment.by_filter(environments):
        print(e.name)
        e.remove_user(keyid)
        print()
