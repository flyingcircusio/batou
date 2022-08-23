def migrate(output):
    """Manual upgrade steps for 2.3."""
    output(
        "Colliding attributes in environment and secrets",
        """

batou will now fail explicitly if an attribute exists both as an environment
override as well as a secret.

You will usually want to delete it from the environment config as that was
being used previously.

        """,
        "manual",
    )
