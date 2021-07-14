from batou.component import Component, Attribute


class ZEO(Component):

    port = Attribute(int, default_conf_string="9001")

    features = ["test", "test2"]
