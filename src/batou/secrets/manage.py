"""Summarize status of secret files."""

from .encryption import EncryptedConfigFile
import glob
import os.path


class Environment(object):

    def __init__(self, path=None, name=None):
        if path:
            self.path = path
            name = os.path.basename(path)
            self.name = os.path.splitext(name)[0]
        else:
            self.name = name
            self.path = "secrets/{}.cfg".format(name)

        self.f = EncryptedConfigFile(
            self.path,
            subfile_pattern="secrets/{}-*".format(self.name),
            write_lock=True,
            quiet=True)
        self.f.__enter__()

    @classmethod
    def all(cls):
        for e in glob.glob("environments/*.cfg"):
            e = e.replace("environments/", "secrets/", 1)
            yield Environment(path=e)

    @classmethod
    def by_filter(cls, filter):
        if filter:
            filter = filter.split(",")
        for e in cls.all():
            if filter and e.name not in filter:
                continue
            yield e

    def summary(self):
        try:
            self.f.read()
        except Exception as e:
            print("\t{}".format(e))
            return
        print("\t members")
        members = self.f.config.get("batou", "members")
        for m in members.value.split(','):
            m = m.strip()
            print("\t\t-", m)
        if not members:
            print("\t\t(none)")
        print("\t secret files")
        files = [f for f in self.f.files if f != self.path]
        files = [
            f.replace('secrets/{}-'.format(self.name), '', 1) for f in files]
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
    if not os.path.exists("secrets"):
        print("No secrets.")

    for e in Environment.all():
        print(e.name)
        e.summary()


def add_user(keyid, environments, **kw):
    """Add a user to a given environment.

    If environments is not given, a user is added
    to all environments.

    """
    if not os.path.exists("secrets"):
        print("No secrets.")

    for e in Environment.by_filter(environments):
        print(e.name)
        e.add_user(keyid)
        print()


def remove_user(keyid, environments, **kw):
    """Remove a user from a given environment.

    If environments is not given, the user is removedd
    from all environments.

    """
    if not os.path.exists("secrets"):
        print("No secrets.")

    for e in Environment.by_filter(environments):
        print(e.name)
        e.remove_user(keyid)
        print()
