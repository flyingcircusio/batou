import os.path

import mock
import pkg_resources
import pytest

from batou.utils import CmdExecutionError

from ..buildout import Buildout
from ..file import File


def buildout(**kw):
    buildout = Buildout(**kw)
    buildout.cmd = mock.Mock()
    return buildout


def test_update_should_pass_config_file_name(root):
    b = buildout(
        python="2.7", setuptools="1.0", config=File("myown.cfg", content="")
    )
    root.component += b
    b.update()

    assert b.cmd.call_count == 1
    calls = iter(x[1][0] for x in b.cmd.mock_calls)
    assert next(calls) == 'bin/buildout -t 3 -c "myown.cfg"'


def test_update_should_pass_custom_timeout(root):
    b = buildout(python="2.7", setuptools="1.0", timeout=40)
    b.update()

    assert b.cmd.call_count == 1
    calls = iter(x[1][0] for x in b.cmd.mock_calls)
    assert next(calls) == 'bin/buildout -t 40 -c "buildout.cfg"'


@pytest.mark.slow
@pytest.mark.timeout(60)
def test_runs_buildout3_successfully(root, output):
    b = Buildout(
        python="3",
        version="3.0.0b1",
        setuptools="54.1.1",
        wheel="0.36.2",
        pip="21.0.1",
        config=File(
            "buildout3.cfg",
            source=pkg_resources.resource_filename(
                __name__, "buildout3-example.cfg"
            ),
        ),
    )
    root.component += b
    try:
        root.component.deploy()
    except CmdExecutionError as e:
        e.report()
        print(output.backend.output)
        raise
    assert os.path.isdir(
        os.path.join(root.environment.workdir_base, "mycomponent/parts")
    )
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, "mycomponent/bin/py")
    )
