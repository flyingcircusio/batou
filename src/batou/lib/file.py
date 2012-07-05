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


class File(Component):

    namevar = 'path'

    ensure = 'file' # or: directory, symlink

    # Content oriented parameters
    content = None
    source = ''
    is_template = False
    template_context = None

    # Unix attributes
    owner = None
    group = None
    mode = None

    # Symlink parameters
    link_source = ''
    link_target = ''

    # Leading directory creation
    leading = False 

    def configure(self):
        self.path = os.path.join(self.workdir, self.path)
        self.path = os.path.normpath(self.path)
        if self.ensure == 'file':
            self += Presence(self.path, leading=self.leading)
        elif self.ensure == 'directory':
            self += Directory(self.path, leading=self.leading)
        elif self.ensure == 'symlink':
            self += Symlink(self.path)
        else:
            raise ValueError(
                'Ensure must be one of: presence, directory, '
                ' symlink not %s' % self.ensure)

        if self.content or self.source or self.is_template:
            if not self.template_context:
                self.template_context = self.parent
            content = Content(self.path,
                              source=self.source,
                              is_template=self.is_template,
                              template_context=self.template_context,
                              content=self.content)
            self += content
            self.content = content.content

        if self.owner:
            self += Owner(self.path, owner=self.owner)

        if self.group:
            self += Group(self.path, group=self.group)

        if self.mode:
            self += Mode(self.path, mode=self.mode)


class Presence(Component):

    namevar = 'path'
    leading = False

    def configure(self):
        if self.leading:
            self += Directory(os.path.dirname(self.path),
                              leading=self.leading)

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
        if self.leading:
            os.makedirs(self.path)
        else:
            os.mkdir(self.path)


class FileComponent(Component):

    namevar = 'path'

    def configure(self):
        self += Presence(self.path)


class Content(FileComponent):

    content = None
    is_template = False
    source = ''
    template_context = None

    def configure(self):
        super(Content, self).configure()
        if not self.template_context:
            self.template_context = self.parent
        if self.content is not None:
            return
        if not self.source:
            self.source = self.path
        if not self.source.startswith('/'):
            self.source = os.path.join(self.root.defdir, self.source)
        if self.is_template:
            self.content = self.template(self.source, self.template_context)
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
