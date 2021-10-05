import difflib
import glob
import grp
import itertools
import json
import os.path
import pwd
import re
import shutil
import stat
import tempfile

import yaml

import batou
from batou import output
from batou.component import Attribute, Component
from batou.utils import dict_merge


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

    namevar = "path"

    ensure = "file"  # or: directory, symlink

    # Content oriented parameters
    content = None
    source = ""
    is_template = True
    template_context = None
    template_args = None  # dict, actually
    encoding = "utf-8"

    # Unix attributes
    owner = None
    group = None
    mode = None

    # Symlink parameters
    link_to = ""

    # Leading directory creation
    leading = False

    # Signal that the content is sensitive data.
    sensitive_data = False

    def configure(self):
        self._unmapped_path = self.path
        self.path = self.map(self.path)
        if self.ensure == "file":
            self += Presence(self.path, leading=self.leading)
        elif self.ensure == "directory":
            self += Directory(
                self.path, leading=self.leading, source=self.source)
        elif self.ensure == "symlink":
            self += Symlink(self.path, source=self.link_to)
        else:
            raise ValueError("Ensure must be one of: file, directory, "
                             "symlink not %s" % self.ensure)
        # variation: content or source explicitly given

        # The mode needs to be set early to allow batou to get out of
        # accidental "permission denied" situations.
        if self.mode:
            self += Mode(self.path, mode=self.mode)

        # no content or source given but file with same name
        # exists
        if self.ensure == "file" and self.content is None and not self.source:
            guess_source = self.root.defdir + "/" + os.path.basename(self.path)
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
            content = Content(
                self.path,
                source=self.source,
                is_template=self.is_template,
                template_context=self.template_context,
                template_args=self.template_args,
                encoding=self.encoding,
                content=self.content,
                sensitive_data=self.sensitive_data,
            )
            self += content
            self.content = content.content

        if self.owner:
            self += Owner(self.path, owner=self.owner)

        if self.group:
            self += Group(self.path, group=self.group)

    @property
    def namevar_for_breadcrumb(self):
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith(".."):
            return relpath
        return os.path.abspath(self.path)

    def last_updated(self, key="st_mtime"):
        if not os.path.exists(self.path):
            return None
        return getattr(os.stat(self.path), key)


class BinaryFile(File):

    is_template = False
    encoding = None


class Presence(Component):

    namevar = "path"
    leading = False

    def configure(self):
        self.path = self.map(self.path)
        if self.leading:
            self += Directory(os.path.dirname(self.path), leading=self.leading)

    def verify(self):
        assert os.path.isfile(self.path)

    def update(self):
        ensure_path_nonexistent(self.path)
        with open(self.path, "w"):
            # We're just touching it.
            pass

    @property
    def namevar_for_breadcrumb(self):
        if isinstance(self.parent, File):
            return os.path.basename(self.path)
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith(".."):
            return relpath
        return os.path.abspath(self.path)

    def last_updated(self, key="st_mtime"):
        if not os.path.exists(self.path):
            return None
        return getattr(os.stat(self.path), key)


class SyncDirectory(Component):

    namevar = "path"
    source = None
    exclude = ()

    verify_opts = "-rclnv"
    sync_opts = "--inplace -lr"

    def configure(self):
        self.path = self.map(self.path)
        self.source = os.path.normpath(
            os.path.join(self.root.defdir, self.source))

    @property
    def exclude_arg(self):
        if not self.exclude:
            return ""
        return " ".join("--exclude '{}'".format(x) for x in self.exclude) + " "

    def verify(self):
        stdout, stderr = self.cmd("rsync {} {}{}/ {}".format(
            self.verify_opts, self.exclude_arg, self.source, self.path))

        # In case of we see non-convergent rsync runs
        output.annotate("rsync result:", debug=True)
        output.annotate(stdout, debug=True)

        if len(stdout.strip().splitlines()) - 4 > 0:
            raise batou.UpdateNeeded()

    def update(self):
        self.cmd("rsync {} {}{}/ {}".format(self.sync_opts, self.exclude_arg,
                                            self.source, self.path))

    @property
    def namevar_for_breadcrumb(self):
        if isinstance(self.parent, Directory):
            return os.path.basename(self.path)
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith(".."):
            return relpath
        return os.path.abspath(self.path)


class Directory(Component):

    namevar = "path"
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

    def last_updated(self, key="st_mtime"):
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
        if not relpath.startswith(".."):
            return relpath
        return os.path.abspath(self.path)


class FileComponent(Component):

    namevar = "path"
    leading = False

    def configure(self):
        self.original_path = self.path
        self.path = self.map(self.original_path)

    @property
    def namevar_for_breadcrumb(self):
        if isinstance(self.parent, File):
            return os.path.basename(self.path)
        relpath = os.path.relpath(self.path, self.environment.base_dir)
        if not relpath.startswith(".."):
            return relpath
        return os.path.abspath(self.path)


def limited_buffer(iterator, limit, lead, separator="...", logdir="/tmp"):
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
    end_buffer = []
    _, diff_log = tempfile.mkstemp(suffix=".diff", dir=logdir)
    diff_log_file = open(diff_log, "a+")
    for line in start_buffer:
        diff_log_file.write(line + "\n")
    try:
        for line in iterator:
            line = line.rstrip()
            diff_log_file.write(line + "\n")
            end_buffer.append(line)
            if len(end_buffer) > lead:
                end_buffer.pop(0)
    finally:
        diff_log_file.close()
    # If we ended up with output in the end buffer, we need to merge the
    # output.
    if end_buffer:
        start_buffer = start_buffer[:lead] + [separator] + end_buffer
        limit_triggered = True

    return start_buffer, limit_triggered, diff_log


class ManagedContentBase(FileComponent):
    """A base class that can be customized for different
    ways of structuring / managing / updating content
    of files.

    Not intended for direct use.
    """

    content = None
    source = ""
    sensitive_data = False

    # If content is given as unicode (always the case with templates)
    # then require it to be encodable. We assume UTF-8 as a sensible default
    # for most use cases and allow overrides.
    encoding = "utf-8"

    _delayed = False
    _max_diff = 200
    _max_diff_lead = 50

    _content_source_attribute = "content"

    def configure(self):
        super(ManagedContentBase, self).configure()

        self.diff_dir = os.path.join(self.environment.workdir_base,
                                     ".batou-diffs")
        # Step 1: Determine content attribute:
        # - it might be given directly (content='...'),
        # - we might have been passed a filename (source='...'), or
        # - we might fall back using the path attribute (namevar)
        if self.source and getattr(self, self._content_source_attribute):
            raise ValueError(
                'Only one of either "{}" or "source" are allowed.',
                format(self._content_source_attribute),
            )

        if not getattr(self, self._content_source_attribute):
            if not self.source:
                self.source = self.original_path

            if not self.source.startswith("/"):
                self.source = os.path.join(self.root.defdir, self.source)

        self._render()

    def _render(self):
        # Phase 1: acquire the source data into self.content
        if self.source:
            if os.path.exists(self.source):
                with open(
                        self.source,
                        "r" if self.encoding else "rb",
                        encoding=self.encoding,
                ) as f:
                    self.content = f.read()
            else:
                if self._delayed:
                    raise FileNotFoundError(
                        "Could not find source file {}".format(self.source))
                # We need to try rendering again later.
                self._delayed = True
                return

        # Phase 2: Decode, if we have an encoding.
        if self.content and self.encoding and not isinstance(
                self.content, str):
            self.content = self.content.decode(self.encoding)

        # Phase 3: We have the source content, now allow a subclass
        # to perform other operations to generate the final output.
        self.render()

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
            with open(self.path, "rb") as target:
                current = target.read()
                if current == self.content:
                    return
        except FileNotFoundError:
            current = b""
        except Exception:
            output.annotate("Unknown content - can't predict diff.")
            raise batou.UpdateNeeded()

        if self.encoding:
            current_text = current.decode(self.encoding, errors="replace")
            wanted_text = self.content.decode(self.encoding, errors="replace")

        if not self.encoding:
            output.annotate("Not showing diff for binary data.", yellow=True)
        elif self.sensitive_data:
            output.annotate(
                "Not showing diff as it contains sensitive data.", red=True)
        else:
            current_lines = current_text.splitlines()
            wanted_lines = wanted_text.splitlines()
            words = set(
                itertools.chain(*(x.split() for x in current_lines),
                                *(x.split() for x in wanted_lines)))
            contains_secrets = bool(
                self.environment.secret_data.intersection(words))

            diff = difflib.unified_diff(current_lines, wanted_lines)
            if not os.path.exists(self.diff_dir):
                os.makedirs(self.diff_dir)
            diff, diff_too_long, diff_log = limited_buffer(
                diff,
                self._max_diff,
                self._max_diff_lead,
                logdir=self.diff_dir)

            if diff_too_long:
                output.line(
                    f"More than {self._max_diff} lines of diff. Showing first "
                    f"and last {self._max_diff_lead} lines.",
                    yellow=True)
                output.line(
                    f"see {diff_log} for the full diff.".format(), yellow=True)
            if contains_secrets:
                output.line(
                    "Not showing diff as it contains sensitive data,",
                    yellow=True)
                output.line(
                    f"see {diff_log} for the diff.".format(), yellow=True)
            else:
                for line in diff:
                    line = line.replace("\n", "")
                    if not line.strip():
                        continue
                    output.annotate(
                        f"  {os.path.basename(self.path)} {line}",
                        red=line.startswith("-"),
                        green=line.startswith("+"))
        raise batou.UpdateNeeded()

    def update(self):
        with open(self.path, "wb") as target:
            target.write(self.content)


class Content(ManagedContentBase):
    """Manage the content of a file - possibly using templating."""

    is_template = File.is_template
    template_context = None
    template_args = None  # dict, actually

    def render(self):
        if not self.is_template:
            return
        if self.template_args is None:
            self.template_args = dict()
        if not self.template_context:
            self.template_context = self.parent
        self.content = self.expand(
            self.content, self.template_context, args=self.template_args)


class JSONContent(ManagedContentBase):

    # Data to be used.
    data = None

    # Data to override the source.
    override = None

    # Cause the rendered data to be human readable. Not all parsers support
    # this so it can be turned off.
    human_readable = True

    # The final content that will be written out to the target.
    content_compact = None
    content_readable = None

    _content_source_attribute = "data"

    def render(self):
        if self.content:
            self.data = json.loads(self.content)
        if self.override:
            self.data = dict_merge(self.data, self.override)

        self.content_compact = json.dumps(
            self.data, sort_keys=True, separators=(",", ":"))
        self.content_readable = json.dumps(self.data, sort_keys=True, indent=4)

        if self.human_readable:
            self.content = self.content_readable
        else:
            self.content = self.content_compact


class YAMLContent(ManagedContentBase):

    # Data to be used.
    data = None

    # Data to override the source.
    override = None

    _content_source_attribute = "data"

    def render(self):
        if self.content:
            self.data = yaml.safe_load(self.content)
        if self.override:
            self.data = dict_merge(self.data, self.override)

        self.content = yaml.safe_dump(self.data)


class Owner(FileComponent):

    owner = None

    def verify(self):
        assert os.path.exists(self.path)
        if isinstance(self.owner, str):
            self.owner = pwd.getpwnam(self.owner).pw_uid
        assert os.stat(self.path).st_uid == self.owner

    def update(self):
        group = os.stat(self.path).st_gid
        os.chown(self.path, self.owner, group)


class Group(FileComponent):

    group = None

    def verify(self):
        assert os.path.exists(self.path)
        if isinstance(self.group, str):
            self.group = grp.getgrnam(self.group).gr_gid
        assert os.stat(self.path).st_gid == self.group

    def update(self):
        owner = os.stat(self.path).st_uid
        os.chown(self.path, owner, self.group)


def convert_mode(string: str) -> int:
    """Convert ls-string representation to bitmask."""
    pattern = re.compile(
        r'''^ # ensure length
        (?P<o400>r|-) # Use groups as octal values.
        (?P<o200>w|-)
        (?P<o100>x|-)
        (?P<o040>r|-)
        (?P<o020>w|-)
        (?P<o010>x|-)
        (?P<o004>r|-)
        (?P<o002>w|-)
        (?P<o001>x|-)
        $ # ensure length''',
        re.VERBOSE,
    )
    match = pattern.match(string)
    if match:
        return sum(
            int(f'0{key}', base=8) for key, value in match.groupdict().items()
            if value != '-')
    else:
        # No match, treat it as wrong syntax
        raise SyntaxError(
            'Mode-string should be between `---------` and `rwxrwxrwx`.')


class Mode(FileComponent):

    mode = Attribute(default=None)

    def configure(self):
        super().configure()

        if isinstance(self.mode, str):
            try:
                self.mode = int(self.mode, 8)
            except ValueError:
                try:
                    self.mode = convert_mode(self.mode)
                except Exception as e:
                    raise batou.ConversionError(self, 'mode', self.mode,
                                                convert_mode, e)

        elif isinstance(self.mode, int):
            pass
        else:
            raise batou.ConfigurationError(
                f'`mode` is required and `{self.mode!r}` is not a valid value.`'
            )

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

    namevar = "target"
    source = None

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

    namevar = "pattern"

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
