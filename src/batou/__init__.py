# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .environment import Environment
from .service import Service, ServiceConfig
from .remote import FabricTask
import inspect
import os.path


def load():
    # Helper to make fabfile more digestable
    caller = inspect.getouterframes(inspect.currentframe())[1]
    base_dir = os.path.dirname(caller[0].f_globals['__file__'])
    config = ServiceConfig(base_dir)
    config.scan()
    fab_commands = caller[0].f_globals
    fab_commands.update(FabricTask.from_config(config))
