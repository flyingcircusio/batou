# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from .environment import Environment
from .service import Service, ServiceConfig


class UpdateNeeded(Exception):
    pass
