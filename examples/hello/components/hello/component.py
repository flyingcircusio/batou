# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from batou.resource.file import File
import batou.template

def mako(filename):
    engine = batou.template.MakoEngine()
    return lambda args:engine.template(os.path.join(
        args['component'].defdir, filename), args)

hello = Component()
hello += File('asdf', template=mako('hello'))
