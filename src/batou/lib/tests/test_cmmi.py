import hashlib
import os.path
import shutil
import sys
import tarfile
import time
from datetime import datetime
from io import BytesIO

import mock
import pytest

from batou.lib.cmmi import Build, Configure, Make
from batou.lib.file import File


def test_build_breadcrumb_shortens_url():
    b = Build(
        "http://launchpad.net/libmemcached/1.0/0.46/"
        "+download/libmemcached-0.46.tar.gz"
    )
    assert b._breadcrumb == "Build('libmemcached-0.46.tar.gz')"


def test_configure_defaults_prefix_to_workdir(root):
    configure = Configure(".")
    configure.cmd = mock.Mock()
    root.component += configure
    assert configure.prefix == root.component.workdir
    root.component.deploy()
    assert (
        " --prefix={}".format(root.component.workdir)
        in configure.cmd.call_args[0][0]
    )


def test_configure_accepts_custom_prefix(root):
    configure = Configure(".", prefix="/asdf")
    configure.cmd = mock.Mock()
    root.component += configure
    assert configure.prefix == "/asdf"
    root.component.deploy()
    assert " --prefix=/asdf" in configure.cmd.call_args[0][0]


def test_configure_verifies_against_success_file(root):
    root.component += File("foo/config.status", content="", leading=True)
    configure = Configure("foo")
    configure.cmd = mock.Mock()
    root.component += configure
    root.component.deploy()
    root.component.deploy()
    assert 1 == configure.cmd.call_count


def test_make_verifies_against_success_file(root):
    root.component += File("foo/Makefile", content="", leading=True)
    make = Make("foo")
    make.cmd = mock.Mock()
    root.component += make
    root.component.deploy()
    root.component.deploy()
    assert 1 == make.cmd.call_count


CONFIGURE = """#!{}
import sys
open('configure-running', 'w').close()

Makefile_template = '''
all:
\ttouch make-all

install:
\ttouch make-install
'''

open('Makefile', 'w').write(Makefile_template)
""".format(
    sys.executable
).encode(
    "ascii"
)


@pytest.fixture
def cmmi_tar(tmpdir):
    # inspired by <http://svn.zope.org/repos/main/zc.recipe.cmmi/trunk
    #              /src/zc/recipe/cmmi/tests.py>
    tarpath = str(tmpdir / "example-build.tgz")
    tar = tarfile.open(tarpath, "w:gz")
    now = time.mktime(datetime.now().timetuple())

    info = tarfile.TarInfo("folder")
    info.type = tarfile.DIRTYPE
    info.mtime = now
    tar.addfile(info)

    info = tarfile.TarInfo("folder/configure")
    info.size = len(CONFIGURE)
    info.mode = 0o755
    info.mtime = now
    tar.addfile(info, BytesIO(CONFIGURE))

    tar.close()

    fixture = type("Dummy", (object,), {})()
    fixture.path = tarpath
    with open(tarpath, "rb") as f:
        fixture.checksum = hashlib.md5(f.read()).hexdigest()
    return fixture


@pytest.mark.slow
def test_runs_cmmi(root, cmmi_tar):
    c = Build(cmmi_tar.path, checksum="md5:" + cmmi_tar.checksum)
    root.component += c

    def copy(uri, target):
        shutil.copyfile(uri, target)
        return target, []

    with mock.patch("batou.lib.download.urlretrieve", new=copy):
        root.component.deploy()

    assert os.path.isfile(
        os.path.join(
            root.environment.workdir_base,
            "mycomponent/example-build/make-install",
        )
    )
