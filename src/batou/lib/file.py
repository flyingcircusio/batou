from batou import output
from batou.component import Component
import batou
import difflib
import glob
import os.path
import pwd
import shutil
import stat
import tempfile


def ensure_path_nonexistent(path):
    if not os.path.lexists(path):
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

    # Signal that the content is sensitive data.
    sensitive_data = False

    def configure(self):
        self._unmapped_path = self.path
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
        if self.ensure == 'file' and self.content is None and not self.source:
            guess_source = (
                self.root.defdir + '/' + os.path.basename(self.path))
            if os.path.isfile(guess_source):
                self.source = guess_source
            else:
                # Avoid the edge case where we want to support a very simple
                # case: specify File('asdf') and have an identical named file
                # in the component definition directory that will be templated
                # to the work directory.
                #
                # However, if you mis-spell the file, then you might
                # accidentally end up with an empty file in the work directory.
                # If you really want an empty File then you can either use
                # Presence(), or (recommended) use File('asdf', content='') to
                # make this explicit. We don't want to accidentally confuse the
                # convenience case (template a simple file) and an edge case
                # (have an empty file)
                raise ValueError(
                    "Missing implicit template file {}. Or did you want "
                    "to create an empty file? Then use File('{}', content='')."
                    .format(guess_source, self._unmapped_path))

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
                              content=self.content,
                              sensitive_data=self.sensitive_data)
            self += content
            self.content = content.content

        if self.owner:
            self += Owner(self.path, owner=self.owner)

        if self.group:
            self += Group(self.path, group=self.group)

    @property
    def namevar_for_breadcrumb(self):
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith('..'):
            return relpath
        return os.path.abspath(self.path)

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
        assert os.path.isfile(self.path)

    def update(self):
        ensure_path_nonexistent(self.path)
        with open(self.path, 'w'):
            # We're just touching it.
            pass

    @property
    def namevar_for_breadcrumb(self):
        if isinstance(self.parent, File):
            return os.path.basename(self.path)
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith('..'):
            return relpath
        return os.path.abspath(self.path)

    def last_updated(self, key='st_mtime'):
        if not os.path.exists(self.path):
            return None
        return getattr(os.stat(self.path), key)


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

        # In case of we see non-convergent rsync runs
        output.annotate('rsync result:', debug=True)
        output.annotate(stdout, debug=True)

        if len(stdout.strip().splitlines()) - 4 > 0:
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd('rsync {} {}{}/ {}'.format(
            self.sync_opts, self.exclude_arg, self.source, self.path))

    @property
    def namevar_for_breadcrumb(self):
        if isinstance(self.parent, Directory):
            return os.path.basename(self.path)
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith('..'):
            return relpath
        return os.path.abspath(self.path)


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
        assert os.path.isdir(self.path)

    def update(self):
        ensure_path_nonexistent(self.path)
        if self.leading:
            os.makedirs(self.path)
        else:
            os.mkdir(self.path)

    def last_updated(self, key='st_mtime'):
        newest = 0  # epoch
        for dirpath, dirnames, filenames in os.walk(self.path):
            for filename in filenames:
                time = getattr(os.stat(os.path.join(dirpath, filename)), key)
                if time > newest:
                    newest = time
        return newest

    @property
    def namevar_for_breadcrumb(self):
        if isinstance(self.parent, File):
            return os.path.basename(self.path)
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith('..'):
            return relpath
        return os.path.abspath(self.path)


class FileComponent(Component):

    namevar = 'path'
    leading = False

    def configure(self):
        self.original_path = self.path
        self.path = self.map(self.original_path)

    @property
    def namevar_for_breadcrumb(self):
        if isinstance(self.parent, File):
            return os.path.basename(self.path)
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith('..'):
            return relpath
        return os.path.abspath(self.path)


def limited_buffer(iterator, limit, lead, separator='...',
                   logdir='/tmp'):
    limit_triggered = False
    # Fill up to limit lines into the start buffer
    start_buffer = []
    for line in iterator:
        line = line.rstrip()
        start_buffer.append(line)
        if len(start_buffer) > limit:
            break

    # Fill the remainder into the end buffer but only keep lead size.
    # This is a memory optimization: don't ever keep the whole iterator in
    # memory!
    started_logging = False
    end_buffer = []
    diff_log = None
    diff_log_file = None
    try:
        for line in iterator:
            line = line.rstrip()
            if not started_logging:
                _, diff_log = tempfile.mkstemp(suffix='.diff', dir=logdir)
                diff_log_file = open(diff_log, 'a+')
                for line in start_buffer:
                    diff_log_file.write(line + '\n')
                started_logging = True
            diff_log_file.write(line + '\n')
            end_buffer.append(line)
            if len(end_buffer) > lead:
                end_buffer.pop(0)
    finally:
        if diff_log_file:
            diff_log_file.close()
    # If we ended up with output in the end buffer, we need to merge the
    # output.
    if end_buffer:
        start_buffer = start_buffer[:lead] + [separator] + end_buffer
        limit_triggered = True

    return start_buffer, limit_triggered, diff_log


class Content(FileComponent):

    content = None
    is_template = File.is_template
    source = ''
    template_context = None
    template_args = None  # dict, actually
    sensitive_data = False

    # If content is given as unicode (always the case with templates)
    # then require it to be encodable. We assume UTF-8 as a sensible default
    # for most use cases and allow overrides.
    encoding = 'utf-8'

    _delayed = False
    _max_diff = 200
    _max_diff_lead = 50

    def configure(self):
        super(Content, self).configure()

        self.diff_dir = os.path.join(
            self.environment.workdir_base, '.batou-diffs')

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
                with open(self.source, 'r' if self.encoding else 'rb',
                          encoding=self.encoding) as f:
                    self.content = f.read()
            else:
                if self._delayed:
                    raise FileNotFoundError(
                        'Could not find source file {}'.format(self.source))
                # We need to try rendering again later.
                self._delayed = True
                return

        # Phase 2: Decode, if we have an encoding.
        if self.encoding and not isinstance(self.content, str):
            self.content = self.content.decode(self.encoding)

        # Phase 3: If we have a template, render it.
        if self.is_template:
            if self.template_args is None:
                self.template_args = dict()
            if not self.template_context:
                self.template_context = self.parent
            self.content = self.expand(
                self.content, self.template_context, args=self.template_args)

        # Phase 4: If we have an encoding, encode the content (again)
        if self.encoding:
            self.content = self.content.encode(self.encoding)

    def verify(self, predicting=False):
        try:
            if self._delayed:
                self._render()
        except FileNotFoundError:
            if predicting:
                # During prediction runs we accept that delayed rending may
                # not yet work and that we will change. We might want to
                # turn this into an explicit flag so we don't implicitly
                # run into a broken deployment.
                assert False
            # If we are not predicting then this is definitely a problem.
            # Stop here.
            raise
        try:
            with open(self.path, 'rb') as target:
                current = target.read()
                if current == self.content:
                    return
        except FileNotFoundError:
            current = b''
        except Exception:
            output.annotate('Unknown content - can\'t predict diff.')
            raise batou.UpdateNeeded()

        if self.encoding:
            current_text = current.decode(self.encoding, errors='replace')
            wanted_text = self.content.decode(self.encoding, errors='replace')

        if not self.encoding:
            output.annotate(
                'Not showing diff for binary data.', yellow=True)
        elif self.sensitive_data:
            output.annotate(
                'Not showing diff as it contains sensitive data.', red=True)
        else:
            diff = difflib.unified_diff(
                    current_text.splitlines(),
                    wanted_text.splitlines())
            if not os.path.exists(self.diff_dir):
                os.makedirs(self.diff_dir)
            diff, diff_too_long, diff_log = limited_buffer(
                diff, self._max_diff, self._max_diff_lead,
                logdir=self.diff_dir)

            if diff_too_long:
                output.line(
                    ('More than {} lines of diff. Showing first and '
                     'last {} lines.'.format(
                        self._max_diff, self._max_diff_lead)), yellow=True)
                output.line(
                    'see {} for the full diff.'.format(diff_log), yellow=True)

            for line in diff:
                line = line.replace('\n', '')
                if not line.strip():
                    continue
                output.annotate(
                    '  {} {}'.format(os.path.basename(self.path), line),
                    red=line.startswith('-'),
                    green=line.startswith('+'))
        raise batou.UpdateNeeded()

    def update(self):
        with open(self.path, 'wb') as target:
            target.write(self.content)


class Owner(FileComponent):

    def verify(self):
        assert os.path.exists(self.path)
        if isinstance(self.owner, str):
            self.owner = pwd.getpwnam(self.owner).pw_uid
        assert os.stat(self.path).st_uid == self.owner

    def update(self):
        group = os.stat(self.path).st_gid
        os.chown(self.path, self.owner, group)


class Group(FileComponent):

    def configure(self):
        super(Group, self).configure()
        if isinstance(self.group, str):
            self.group = pwd.getpwnam(self.group)

    def verify(self):
        assert os.path.exists(self.path)
        assert os.stat(self.path).st_gid == self.group

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
        assert os.path.lexists(self.path)
        current = self._stat(self.path).st_mode
        assert stat.S_IMODE(current) == self.mode

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
        assert os.path.islink(self.target)
        assert os.readlink(self.target) == self.source

    def update(self):
        ensure_path_nonexistent(self.target)
        os.symlink(self.source, self.target)


class Purge(Component):
    """Ensure that a set of files (given as a glob) does not exist."""

    namevar = 'pattern'

    def configure(self):
        self.pattern = self.map(self.pattern)

    def verify(self):
        assert not glob.glob(self.pattern)

    def update(self):
        for filename in glob.glob(self.pattern):
            if os.path.isdir(filename):
                shutil.rmtree(filename)
            else:
                os.remove(filename)
