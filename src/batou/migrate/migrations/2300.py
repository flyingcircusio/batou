from batou.utils import get_output


def migrate(output):
    """Manual upgrade steps for 2.3."""
    candidates = get_output(
        'grep "Adddress" * -nIr | egrep -v "import"', "<no candidates found>"
    )
    output(
        "Address objects now only resolve IPv4 addresses by default",
        f"""

If you use IPv6 then you have to enable it explicitly by setting
`require_v6=True`.

Candidates:

{candidates}
        """,
        "manual",
    )

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
