from batou.component import Component, Attribute


class Component7(Component):
    # Separate components.py as error would render components from
    # component1/component.py as missing

    only_one_default = Attribute("literal", False, "False")
