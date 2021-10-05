from batou.component import Attribute, Component


class ZEO(Component):

    port = Attribute(int, default_conf_string="9001")

    features = ["test", "test2"]
