from batou.utils import get_output


def migrate(output):
    candidates = get_output(
        'grep "Adddress" * -nIr | egrep -v "import"', "<no candidates found>"
    )
    output(
        "Address objects now only resolve IPv4 addresses by default",
        f"""

        If you use IPv6 then you have to enable it explicitly by setting
        `require_v6=True`. If you want the old behaviour you can use
        `require_v6='optional'`.

        You can also set new defaults per environment settings which allows
        you to return to the previous behaviour of IPv6 being optional without
        touching component code:

        [environment]
        require_v4 = True
        require_v6 = optional

        Candidates:

        {candidates}
        """,
        "manual",
    )
