from batou.component import Component, Attribute


class ZEO(Component):

    port = Attribute(int, '9001')

    features = ['test', 'test2']
