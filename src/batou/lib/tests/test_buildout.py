import os.path
import pathlib
import sys

import mock
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
@pytest.mark.skipif(
    sys.version_info >= (3, 7),
    reason="python 2.7 only available in tests with python 3.6",
)
def test_runs_buildout_successfully(root):
    b = Buildout(
        python="2.7",
        version="2.13.4",
        setuptools="44.1.1",
        config=File(
            "buildout.cfg",
            source=pathlib.Path(__file__).parent / "buildout-example.cfg",
        ),
    )
    root.component += b
    root.component.deploy()
    assert os.path.isdir(
        os.path.join(root.environment.workdir_base, "mycomponent/parts")
    )
    assert os.path.isfile(
        os.path.join(root.environment.workdir_base, "mycomponent/bin/py")
    )


@pytest.mark.slow
@pytest.mark.timeout(60)
def test_runs_buildout3_successfully(root, output):
    b = Buildout(
        python="3",
        version="3.0.1",
        setuptools="68.0.0",
        wheel="0.36.2",
        pip="23.3.2",
        config=File(
            "buildout3.cfg",
            source=str(pathlib.Path(__file__).parent / "buildout3-example.cfg"),
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
