# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

import mock


def buildout(**kw):
    from ..buildout import Buildout
    buildout = Buildout(**kw)
    buildout.cmd = mock.Mock()
    return buildout


def test_update_should_pass_config_file_name(root):
    from ..file import File
    b = buildout(
        python='2.7',
        config=File('myown.cfg'))
    root.component += b
    b.update()

    assert b.cmd.call_count == 1
    calls = iter(x[1][0] for x in b.cmd.mock_calls)
    assert calls.next() == 'bin/buildout -t 3 -c "myown.cfg"'


def test_update_should_pass_custom_timeout(root):
    b = buildout(
        python='2.7',
        timeout=40)
    b.update()

    assert b.cmd.call_count == 1
    calls = iter(x[1][0] for x in b.cmd.mock_calls)
    assert calls.next() == 'bin/buildout -t 40 -c "buildout.cfg"'
