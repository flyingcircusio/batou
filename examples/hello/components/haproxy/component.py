# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.lib import haproxy
from batou.component import Component


class HAProxy(haproxy.HAProxy):

    backend_hook = 'deliverance:http'
