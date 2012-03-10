# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import grp
import logging
import os.path
import pwd
import shutil
import stat

logger = logging.getLogger(__name__)


class File(object):

    # meta-parameters
    changed = False     # Updated if commit changed anything
    id = None   # <env>/<host>/<resourcetype>/<id> are to be globally unique

    def __init__(self, path, content=None, template=None, owner=None,
                 group=None, mode=0664):
        self.id = self.path = path
        self.content = content
        self.template = template
        self.owner = owner
        self.group = group
        self.mode = mode

    def prepare(self, env={}):
        """Prepare all attributes to reflect the target state."""
        # Compute content from template if necessary
        if self.template:
            self.content = self.template(env)

        # Turn user and group names into IDs if necessary
        if isinstance(self.owner, str):
            self.owner = pwd.getpwnam(self.owner)
        if isinstance(self.group, str):
            self.group = grp.getgrnam(self.group)

        self.mode = 0100000 | self.mode

    def commit(self):
        """Commit all attributes to the actual file."""
        self._clean()
        self._create()
        self._update()

    @property
    def stat(self):
        return os.stat(self.path)

    def _clean(self):
        # Remove whatever is there if it's not a file.
        if not os.path.exists(self.path) or os.path.isfile(self.path):
            return
        if os.path.isdir(self.path):
            logger.debug('Cleaning by removing directory')
            shutil.rmtree(self.path)
        logger.debug('Cleaning by removing other file')
        os.unlink(self.path)

    def _create(self):
        # Create the file, if it doesn't exist
        if os.path.isfile(self.path):
            return
        logger.debug('Creating new file')
        open(self.path, 'w').close()

    def _update(self):
        # Content
        if self.content:
            content = open(self.path, 'r').read()
            if content != self.content:
                logger.debug('Updating content')
                open(self.path, 'w').write(self.content)

        if self.owner:
            if self.stat.uid != self.owner:
                logger.debug('Updating owner')
                os.chown(self.path, self.owner, self.stat.gid)
        if self.group:
            if self.stat.gid != self.group:
                logger.debug('Updating group')
                os.chown(self.path, self.stat.uid, self.group)

        # Mode
        if self.mode:
            if self.stat.st_mode != self.mode:
                logger.debug('Updating mode: %s -> %s' %
                             (oct(self.stat.st_mode), oct(self.mode)))
                os.chmod(self.path, self.mode)
