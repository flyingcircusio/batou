# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .environment import Environment
from .service import Service, ServiceConfig

# Ensure platform components have a chance to register.
# XXX make more flexible.
import batou.lib.goceptnet

class UpdateNeeded(Exception):
    pass
