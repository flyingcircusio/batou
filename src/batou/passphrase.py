# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

"""Query passphrase from user and put it into a temporary file"""

from __future__ import print_function, unicode_literals
import getpass
import os
import tempfile


class PassphraseFile(object):
    """Context that provides a passphrase in a temporary file.

    The passphrase is queried from the user. Avoid repeated passphrase
    queries by caching entered passphrases.
    """

    passphrase_file = None
    passphrase_cache = {}

    def __init__(self, for_what, double_entry=False):
        """Setup passphrase file wrapper. `for_what` describes the object that
        is protected via this passphrase (presented to the user during
        passphrase entry). If `double_entry` is True, the passphrase must be
        entered twice.
        """
        self.for_what = for_what
        self.double_entry = double_entry

    def __enter__(self):
        self.passphrase_file = tempfile.NamedTemporaryFile(
            prefix='passphrase.', delete=False)
        print(self._get_passphrase(), file=self.passphrase_file)
        self.passphrase_file.close()
        return self.passphrase_file.name

    def _get_passphrase(self):
        if self.for_what in self.passphrase_cache:
            return self.passphrase_cache[self.for_what]
        if self.double_entry:
            phrase = self.ask_passphrase_twice()
        else:
            phrase = self.ask_passphrase_once()
        self.passphrase_cache[self.for_what] = phrase
        return phrase

    def ask_passphrase_once(self):
        return getpass.getpass('Enter passphrase for %s: ' % self.for_what)

    def ask_passphrase_twice(self):
        phrase1 = getpass.getpass('Enter passphrase for %s: ' % self.for_what)
        if len(phrase1) < 20:
            raise RuntimeError(
                'passphrase must be at least 20 characters long')
        phrase2 = getpass.getpass(
            'Enter passphrase for %s again: ' % self.for_what)
        if phrase1 != phrase2:
            raise RuntimeError('passphrases do not match')
        return phrase1

    def __exit__(self, *_exc_args):
        os.unlink(self.passphrase_file.name)
