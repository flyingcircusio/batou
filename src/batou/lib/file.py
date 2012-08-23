from batou.component import Component
import batou
import logging
import os.path
import pwd
import shutil
import stat

logger = logging.getLogger(__name__)


def ensure_path_nonexistent(path):
    try:
        # cannot use os.path.exists(), since we also want to remove broken
        # symlinks
        os.lstat(path)
    except OSError:
        return
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


class File(Component):

    namevar = 'path'

    ensure = 'file'  # or: directory, symlink

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
    link_to = ''

    # Leading directory creation
    leading = False

    def configure(self):
        self.fullpath = os.path.normpath(
                os.path.join(self.workdir, self.path))
        if self.ensure == 'file':
            self += Presence(self.path, leading=self.leading)
        elif self.ensure == 'directory':
            self += Directory(self.path,
                              leading=self.leading,
                              source=self.source)
        elif self.ensure == 'symlink':
            self += Symlink(self.path, source=self.link_to)
        else:
            raise ValueError(
                'Ensure must be one of: file, directory, '
                'symlink not %s' % self.ensure)

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
    leading = False
    source = None

    def configure(self):
        self.fullpath = os.path.normpath(
                os.path.join(self.workdir, self.path))
        if self.source:
            self.source = os.path.normpath(
                os.path.join(self.root.defdir, self.source))

    def verify(self):
        if not os.path.isdir(self.path):
            raise batou.UpdateNeeded()
        if self.source:
            stdout, stderr = self.cmd('rsync -anv {}/ {}'.format(
                self.source, self.fullpath))
            if len(stdout.splitlines()) - 4 > 0:
                raise batou.UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.path)
        if self.leading:
            os.makedirs(self.path)
        else:
            os.mkdir(self.path)
        if self.source:
            self.cmd('rsync -a {}/ {}'.format(self.source, self.fullpath))


class FileComponent(Component):

    namevar = 'path'
    leading = False

    def configure(self):
        self += Presence(self.path, leading=self.leading)


class Content(FileComponent):

    content = None
    is_template = False
    source = ''
    template_context = None

    def configure(self):
        super(Content, self).configure()

        # Step 1: Determine content attribute:
        # - it might be given directly (content='...'),
        # - we might have been passed a filename (source='...'), or
        # - we might fall back using the path attribute (namevar)
        if self.source and self.content:
            raise ValueError(
                'Only one of either "content" or "source" are allowed.')
        if not self.content:
            if not self.source:
                self.source = self.path
            if not self.source.startswith('/'):
                self.source = os.path.join(self.root.defdir, self.source)
            with open(self.source, 'r') as f:
                self.content = f.read()

        # Step 2: If our content is a template then render it.
        if not self.is_template:
            return
        if not self.template_context:
            self.template_context = self.parent
        self.content = self.expand(self.content, self.template_context)

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

    def verify(self):
        try:
            self._select_stat_implementation()
        except AttributeError:
            # Happens on systems without lstat/lchmod implementation (like
            # Linux) Not sure whether ignoring it is really the right thing.
            return
        current = self._stat(self.path).st_mode
        if stat.S_IMODE(current) != self.mode:
            raise batou.UpdateNeeded()

    def update(self):
        self._chmod(self.path, self.mode)

    def _select_stat_implementation(self):
        self._stat = os.stat
        self._chmod = os.chmod
        if os.path.islink(self.path):
            self._stat = os.lstat
            self._chmod = os.lchmod


class Symlink(Component):

    namevar = 'target'

    def configure(self):
        self.source = os.path.join(self.workdir, self.source)

    def verify(self):
        if not os.path.islink(self.target):
            raise batou.UpdateNeeded()
        if os.readlink(self.target) != self.source:
            raise batou.UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.target)
        os.symlink(self.source, self.target)
