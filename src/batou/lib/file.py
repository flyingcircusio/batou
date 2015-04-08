from batou import output
from batou.component import Component
import batou
import difflib
import glob
import os.path
import pwd
import shutil
import stat


def ensure_path_nonexistent(path):
    try:
        # cannot use os.path.exists(), since we also want to remove broken
        # symlinks
        os.lstat(path)
    except OSError:
        return
    if os.path.islink(path):
        os.unlink(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


class File(Component):

    namevar = 'path'

    ensure = 'file'  # or: directory, symlink

    # Content oriented parameters
    content = None
    source = ''
    is_template = True
    template_context = None
    template_args = None  # dict, actually
    encoding = 'utf-8'

    # Unix attributes
    owner = None
    group = None
    mode = None

    # Symlink parameters
    link_to = ''

    # Leading directory creation
    leading = False

    def configure(self):
        self.path = self.map(self.path)
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
        # variation: content or source explicitly given

        # The mode needs to be set early to allow batou to get out of
        # accidental "permission denied" situations.
        if self.mode:
            self += Mode(self.path, mode=self.mode)

        # no content or source given but file with same name
        # exists
        if self.ensure == 'file' and not self.content and not self.source:
            guess_source = (
                self.root.defdir + '/' + os.path.basename(self.path))
            if os.path.isfile(guess_source):
                self.source = guess_source

        if self.content or self.source:
            if self.template_args is None:
                self.template_args = dict()
            if not self.template_context:
                self.template_context = self.parent
            content = Content(self.path,
                              source=self.source,
                              is_template=self.is_template,
                              template_context=self.template_context,
                              template_args=self.template_args,
                              encoding=self.encoding,
                              content=self.content)
            self += content
            self.content = content.content

        if self.owner:
            self += Owner(self.path, owner=self.owner)

        if self.group:
            self += Group(self.path, group=self.group)

    @property
    def namevar_for_breadcrumb(self):
        return os.path.relpath(self.path, self.environment.base_dir)

    def last_updated(self, key='st_mtime'):
        if not os.path.exists(self.path):
            return None
        return getattr(os.stat(self.path), key)


class BinaryFile(File):

    is_template = False
    encoding = None


class Presence(Component):

    namevar = 'path'
    leading = False

    def configure(self):
        self.path = self.map(self.path)
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

    @property
    def namevar_for_breadcrumb(self):
        return os.path.relpath(self.path, self.environment.base_dir)


class SyncDirectory(Component):

    namevar = 'path'
    source = None
    exclude = ()

    verify_opts = '-rclnv'
    sync_opts = '--inplace -lr'

    def configure(self):
        self.path = self.map(self.path)
        self.source = os.path.normpath(
            os.path.join(self.root.defdir, self.source))

    @property
    def exclude_arg(self):
        if not self.exclude:
            return ''
        return ' '.join("--exclude '{}'".format(x) for x in self.exclude) + ' '

    def verify(self):
        stdout, stderr = self.cmd('rsync {} {}{}/ {}'.format(
            self.verify_opts, self.exclude_arg, self.source, self.path))
        if len(stdout.strip().splitlines()) - 4 > 0:
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd('rsync {} {}{}/ {}'.format(
            self.sync_opts, self.exclude_arg, self.source, self.path))

    @property
    def namevar_for_breadcrumb(self):
        return os.path.relpath(self.path, self.environment.base_dir)


class Directory(Component):

    namevar = 'path'
    leading = False
    source = None
    exclude = ()

    def configure(self):
        self.path = self.map(self.path)
        if self.source:
            # XXX The ordering is wrong. SyncDirectory should run *after*.
            self += SyncDirectory(
                self.path, source=self.source, exclude=self.exclude)

    def verify(self):
        if not os.path.isdir(self.path):
            raise batou.UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.path)
        if self.leading:
            os.makedirs(self.path)
        else:
            os.mkdir(self.path)

    def last_updated(self, key='st_mtime'):
        newest = None
        for dirpath, dirnames, filenames in os.walk(self.path):
            for filename in filenames:
                time = getattr(os.stat(os.path.join(dirpath, filename)), key)
                if time > newest:
                    newest = time
        return newest

    @property
    def namevar_for_breadcrumb(self):
        return os.path.relpath(self.path, self.environment.base_dir)


class FileComponent(Component):

    namevar = 'path'
    leading = False

    def configure(self):
        self.original_path = self.path
        self.path = self.map(self.original_path)

    @property
    def namevar_for_breadcrumb(self):
        return os.path.relpath(self.path, self.environment.base_dir)


class Content(FileComponent):

    content = None
    is_template = File.is_template
    source = ''
    template_context = None
    template_args = None  # dict, actually

    # If content is given as unicode (always the case with templates)
    # then require it to be encodable. We assume UTF-8 as a sensible default
    # for most use cases and allow overrides.
    encoding = 'utf-8'

    _delayed = False

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
                self.source = self.original_path

            if not self.source.startswith('/'):
                self.source = os.path.join(self.root.defdir, self.source)

        self._render()

    def _render(self):
        # Phase 1: acquire the source data into self.content
        if self.source:
            if os.path.exists(self.source):
                with open(self.source, 'r') as f:
                    self.content = f.read()
            else:
                if self._delayed:
                    raise RuntimeError(
                        'Could not find file {}'.format(self.source))
                # We need to try rendering again later.
                self._delayed = True
                return

        # Phase 2: Decode, if we have an encoding.
        if self.encoding and not isinstance(self.content, unicode):
            self.content = self.content.decode(self.encoding)

        # Phase 3: If we have a template, render it.
        if self.is_template:
            if self.template_args is None:
                self.template_args = dict()
            if not self.template_context:
                self.template_context = self.parent
            self.content = self.expand(
                self.content, self.template_context, args=self.template_args)

        # Phase 4: If we have an encoding, encode the content again
        if self.encoding:
            self.content = self.content.encode(self.encoding)

    def verify(self):
        if self._delayed:
            self._render()
        with open(self.path, 'r') as target:
            current = target.read()
            if current != self.content:
                for line in difflib.unified_diff(current.splitlines(),
                                                 self.content.splitlines()):
                    output.annotate(line, debug=True)
                raise batou.UpdateNeeded()

    def update(self):
        with open(self.path, 'w') as target:
            target.write(self.content)


class Owner(FileComponent):

    def verify(self):
        if isinstance(self.owner, str):
            self.owner = pwd.getpwnam(self.owner).pw_uid
        current = os.stat(self.path).st_uid
        if current != self.owner:
            raise batou.UpdateNeeded()

    def update(self):
        group = os.stat(self.path).st_gid
        os.chown(self.path, self.owner, group)


class Group(FileComponent):

    def configure(self):
        super(Group, self).configure()
        if isinstance(self.group, str):
            self.group = pwd.getpwnam(self.group)

    def verify(self):
        current = os.stat(self.path).st_gid
        if current != self.group:
            raise batou.UpdateNeeded()

    def update(self):
        owner = os.stat(self.path).st_uid
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
        self.target = self.map(self.target)
        self.source = self.map(self.source)

    def verify(self):
        if not os.path.islink(self.target):
            raise batou.UpdateNeeded()
        if os.readlink(self.target) != self.source:
            raise batou.UpdateNeeded()

    def update(self):
        ensure_path_nonexistent(self.target)
        os.symlink(self.source, self.target)


class Purge(Component):
    """Ensure that a set of files (given as a glob) does not exist."""

    namevar = 'pattern'

    def configure(self):
        self.pattern = self.map(self.pattern)

    def verify(self):
        if glob.glob(self.pattern):
            raise batou.UpdateNeeded()

    def update(self):
        for filename in glob.glob(self.pattern):
            os.unlink(filename)
