from batou.component import Attribute, Component, ConfigString


class ZEO(Component):

    port = Attribute(int, default=ConfigString("9001"))

    features = ["test", "test2"]
