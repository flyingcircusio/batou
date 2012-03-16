# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.component import Component
import batou
import grp
import logging
import os.path
import pwd
import shutil
import stat

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
            raise batou.UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.path)
        with open(self.path, 'w'):
            # We're just touching it.
            pass


class Directory(Component):

    namevar = 'path'

    def verify(self):
        if not os.path.isdir(self.path):
            raise batou.UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.path)
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
            with open(self.source, 'r') as source:
                self.content = source.read()

    def verify(self):
        with open(self.path, 'r') as target:
            if target.read() != self.content:
                raise batou.UpdateNeeded()

    def update(self):
        with open(self.path, 'w') as target:
            target.write(self.content)


class Owner(FileComponent):

    def configure(self):
        super(Owner, self).configure()
        if isinstance(self.owner, str):
            self.owner = pwd.getpwnam(self.owner)

    def verify(self):
        current = os.stat(self.path).uid
        if current != self.owner:
            raise batou.UpdateNeeded()

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
            raise batou.UpdateNeeded()

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
            raise batou.UpdateNeeded()

    def update(self):
        os.chmod(self.path, self.mode)


class Symlink(Component):

    namevar = 'target'

    def configure(self):
        if not self.source.startswith('/'):
            self.source = os.path.join(self.root.defdir, self.source)

    def verify(self):
        if not os.path.islink(self.target):
            raise batou.UpdateNeeded()
        if os.path.realpath(self.target) != self.source:
            raise batou.UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.target)
        os.symlink(self.source, self.target)
