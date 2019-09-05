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
            self.path = 'secrets/{}.cfg'.format(name)

        self.f = EncryptedConfigFile(self.path, write_lock=True, quiet=True)
        self.f.__enter__()

    @classmethod
    def all(cls):
        for e in glob.glob('secrets/*.cfg'):
            yield Environment(path=e)

    @classmethod
    def by_filter(cls, filter):
        if filter:
            filter = filter.split(',')
        for e in cls.all():
            if filter and e.name not in filter:
                continue
            yield e

    def summary(self):
        try:
            self.f.read()
        except Exception:
            print("\t<Can not decrypt. You seem to not have access.>")
            return
        print("\t", self.f.config.get('batou', 'members'))

    def add_user(self, keyid):
        try:
            self.f.read()
        except Exception:
            print("\t<Can not decrypt. You seem to not have access.>")
            return
        members = self.f.get_members()
        if keyid not in members:
            members.append(keyid)
            self.f.set_members(members)
            try:
                self.f.write_config()
            except Exception:
                print("\t<Can not encrypt. You seem to be missing a key.>")
                return
        self.summary()

    def remove_user(self, keyid):
        try:
            self.f.read()
        except Exception:
            print("\t<Can not decrypt. You seem to not have access.>")
            return
        members = self.f.get_members()
        if keyid in members:
            members.remove(keyid)
            self.f.set_members(members)
            try:
                self.f.write_config()
            except Exception:
                print("\t<Can not encrypt. You seem to be missing a key.>")
                return
        self.summary()


def summary(**kw):
    """Secrets editor console script.

    The main focus here is to avoid having unencrypted files accidentally
    ending up in the deployment repository.

    """
    if not os.path.exists('secrets'):
        print("No secrets.")

    for e in Environment.all():
        print(e.name)
        e.summary()
        print()


def add_user(keyid, environments, **kw):
    """Add a user to a given environment.

    If environments is not given, a user is added
    to all environments.

    """
    if not os.path.exists('secrets'):
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
    if not os.path.exists('secrets'):
        print("No secrets.")

    for e in Environment.by_filter(environments):
        print(e.name)
        e.remove_user(keyid)
        print()
