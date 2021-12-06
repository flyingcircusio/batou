import os

from batou.migrate import main


def test_2300__1(tmp_path, capsys):
    """It informs about changes in Attribute, Address and secrets."""
    os.chdir(tmp_path)
    main()
    expected = ['Version: 2300', 'Attribute', 'Address', 'secrets']
    output = capsys.readouterr().out
    for term in expected:
        assert term in output
