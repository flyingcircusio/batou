from batou.component import Attribute, Component


class Component7(Component):
    # Separate components.py as error would render components from
    # component1/component.py as missing

    only_one_default = Attribute(
        "literal", default=False, default_conf_string="False"
    )
