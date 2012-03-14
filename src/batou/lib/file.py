# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import grp
import logging
import os.path
import pwd
import shutil
import stat

from batou import UpdateNeeded
from batou.component import Component

logger = logging.getLogger(__name__)


def ensure_path_nonexistent(path):
    if not os.path.exists(path):
        return
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


class Presence(Component):

    namevar = 'path'

    def verify(self):
        if not os.path.isfile(self.path):
            raise UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.path)
        open(self.path, 'w').close()


class Directory(Component):

    namevar = 'path'

    def verify(self):
        if not os.path.isdir(self.path):
            raise UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(path)
        os.makedirs(self.path)


class FileComponent(Component):

    namevar = 'path'

    def configure(self):
        self += Presence(self.path)


class Content(FileComponent):

    content = None
    is_template = False
    source = ''

    def configure(self):
        super(Content, self).configure()
        if self.content is not None:
            return
        if not self.source.startswith('/'):
            self.source = os.path.join(self.root.defdir, self.path)
        if self.is_template:
            self.content = self.template(self.source, self.parent)
        else:
            self.content = open(self.source, 'r').read()


    def verify(self):
        current = open(self.path, 'r').read()
        if current != self.content:
            raise UpdateNeeded()

    def update(self):
        open(self.path, 'w').write(self.content)


class Owner(FileComponent):

    def configure(self):
        super(Owner, self).configure()
        if isinstance(self.owner, str):
            self.owner = pwd.getpwnam(self.owner)

    def verify(self):
        current = os.stat(self.path).uid
        if current != self.owner:
            raise UpdateNeeded()

    def update(self):
        group = os.stat(self.path).gid
        os.chown(self.path, self.owner, group)


class Group(FileComponent):

    def configure(self):
        super(Group, self).configure()
        if isinstance(self.group, str):
            self.group = pwd.getpwnam(self.group)

    def verify(self):
        current = os.stat(self.path).gid
        if current != self.group:
            raise UpdateNeeded()

    def update(self):
        owner = os.stat(self.path).uid
        os.chown(self.path, owner, self.group)


class Mode(FileComponent):

    def configure(self):
        super(Mode, self).configure()
        self.mode = 0o100000 | self.mode

    def verify(self):
        current = os.stat(self.path).st_mode
        if current != self.mode:
            raise UpdateNeeded()

    def update(self):
        os.chmod(self.path, self.mode)


class Symlink(Component):

    namevar = 'target'

    def configure(self):
        if not self.source.startswith('/'):
            self.source = os.path.join(self.root.defdir, self.source)

    def verify(self):
        if not os.path.islink(self.target):
            raise UpdateNeeded()
        if os.path.realpath(self.target) != self.source:
            raise UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.target)
        os.symlink(self.source, self.target)
