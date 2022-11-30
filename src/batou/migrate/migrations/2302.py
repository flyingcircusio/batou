from batou.utils import get_output


def migrate(output):
    """Manual upgrade steps for 2.3. (updated)"""
    candidates = get_output(
        'grep "Attribute" * -nIr | egrep -v "import"', "<no candidates found>"
    )
    output(
        "`Attribute` defaults now require `ConfigString` for expansion, "
        "mapping, and conversion.",
        f"""

We previously always interpreted strings in attribute defaults as
"config strings" that were passed to the factory/conversion function. However,
there was no way out if the target type was already a string and no
conversion should happen.

You need to review your Attribute usages whether any default strings need to be
encased in `batou.component.ConfigString(x)`.

Candidates:

{candidates}

If you are using `batou_ext`, you will also need to update to a current version
supporting batou 2.3.

        """,
    )
