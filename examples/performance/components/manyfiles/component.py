# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.component import Component
from batou.lib import file


class ManyFiles(Component):

    amount = 10000

    def configure(self):
        for x in range(self.amount):
            self += file.Content('file%s' % x, content='Hello world')
