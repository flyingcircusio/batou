from batou.component import Component
from batou.utils import Attribute


class ZEO(Component):

    port = Attribute(int, 9001)

    features = ['test', 'test2']
