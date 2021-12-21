def migrate(output):
    """Manual upgrade steps for 2.3."""
    output(
        'Change Address init parameters', """
        The new default DNS resolve scheme will resolve IPv4 by default. If
        you want IPv6 you have to set that explicitly. Please adapt all
        occurrences of `Address` in you components and explicitly set
        `require_v6` and `require_v4`.""")
    output(
        'Colliding attributes in environment and secrets', """
        If an attribute exists in secrets and also in plain text
        environment config, batou fails. Delete it from plain text.""")
    output(
        '`Attribute` requires explicit default.', """
        Default values for `Attribute` have to be passed either with
        `default` or `default_conf_string` as keyword argument. If you use
        `batou_ext`, update to a current version.""")
