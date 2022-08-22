def migrate(output):
    """Manual upgrade steps for 2.3. (updated)"""
    output(
        "`Attribute` defaults require `ConfigString` for expansion, "
        "mapping, and conversion.",
        """
        Default values for `Attribute` have to be passed as `ConfigString`
        if you want conversions to take place. Plain strings will not
        be converted any longer.
        If you use `batou_ext`, update to a current version.""",
    )
