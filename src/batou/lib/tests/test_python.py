from batou.component import Component
from batou.lib.python import VirtualEnv
from batou.update import update_bootstrap
import os
import pytest
import sys
from batou.utils import cmd


@pytest.mark.slow
@pytest.mark.timeout(120)
def test_package_venv_installations(root):
    # this is a really nasty test ...
    bin_dir = os.path.dirname(sys.executable)
    base_dir = os.path.dirname(bin_dir)

    # copy the "venv" example
    cmd('cp -a {}/examples/venvs/* .'.format(base_dir))
    cmd('rm -rf work')

    # ensure the dev link is OK
    update_bootstrap('', base_dir)

    # run batou, hope for the best. ;)
    stdout, stderr = cmd('./batou local dev localhost')
    assert sorted(stdout.split("\n")) == sorted("""\
Updating Py26 > Buildout > File(work/py26/buildout.cfg) > \
Presence(work/py26/buildout.cfg)
Updating Py26 > Buildout > File(work/py26/buildout.cfg) > \
Content(work/py26/buildout.cfg)
Updating Py26 > Buildout > VirtualEnv(2.6) > VirtualEnvPy2_6 > \
VirtualEnvDownload(1.10.1) > Download(http://pypi.gocept.com/packages/\
source/v/virtualenv/virtualenv-1.10.1.tar.gz)
Updating Py26 > Buildout > VirtualEnv(2.6) > VirtualEnvPy2_6 > \
VirtualEnvDownload(1.10.1) > Extract(virtualenv-1.10.1.tar.gz) > \
Untar(virtualenv-1.10.1.tar.gz)
Updating Py26 > Buildout > VirtualEnv(2.6) > VirtualEnvPy2_6
Updating Py26 > Buildout > VirtualEnv(2.6) > Package(setuptools==1.4.1)
Updating Py26 > Buildout > VirtualEnv(2.6) > Package(zc.buildout==2.2.1)
Updating Py26 > Buildout
Updating Py27 > Buildout > File(work/py27/buildout.cfg) > \
Presence(work/py27/buildout.cfg)
Updating Py27 > Buildout > File(work/py27/buildout.cfg) > \
Content(work/py27/buildout.cfg)
Updating Py27 > Buildout > VirtualEnv(2.7) > VirtualEnvPy2_7
Updating Py27 > Buildout > VirtualEnv(2.7) > Package(setuptools==1.4.1)
Updating Py27 > Buildout > VirtualEnv(2.7) > Package(zc.buildout==2.2.1)
Updating Py27 > Buildout
Updating Py33 > Buildout > File(work/py33/buildout.cfg) > \
Presence(work/py33/buildout.cfg)
Updating Py33 > Buildout > File(work/py33/buildout.cfg) > \
Content(work/py33/buildout.cfg)
Updating Py33 > Buildout > VirtualEnv(3.3) > VirtualEnvPy3_3
Updating Py33 > Buildout > VirtualEnv(3.3) > Package(setuptools==1.4.1)
Updating Py33 > Buildout > VirtualEnv(3.3) > Package(zc.buildout==2.2.1)
Updating Py33 > Buildout
Updating Py32 > Buildout > File(work/py32/buildout.cfg) > \
Presence(work/py32/buildout.cfg)
Updating Py32 > Buildout > File(work/py32/buildout.cfg) > \
Content(work/py32/buildout.cfg)
Updating Py32 > Buildout > VirtualEnv(3.2) > VirtualEnvPy3_2
Updating Py32 > Buildout > VirtualEnv(3.2) > Package(setuptools==1.4.1)
Updating Py32 > Buildout > VirtualEnv(3.2) > Package(zc.buildout==2.2.1)
Updating Py32 > Buildout
Updating Py24 > Buildout > File(work/py24/buildout.cfg) > \
Presence(work/py24/buildout.cfg)
Updating Py24 > Buildout > File(work/py24/buildout.cfg) > \
Content(work/py24/buildout.cfg)
Updating Py24 > Buildout > VirtualEnv(2.4) > VirtualEnvPy2_4 > \
VirtualEnvDownload(1.7.2) > Download(http://pypi.gocept.com/packages/\
source/v/virtualenv/virtualenv-1.7.2.tar.gz)
Updating Py24 > Buildout > VirtualEnv(2.4) > VirtualEnvPy2_4 > \
VirtualEnvDownload(1.7.2) > Extract(virtualenv-1.7.2.tar.gz) > \
Untar(virtualenv-1.7.2.tar.gz)
Updating Py24 > Buildout > VirtualEnv(2.4) > VirtualEnvPy2_4
Updating Py24 > Buildout > VirtualEnv(2.4) > Package(setuptools==1.3.2)
Updating Py24 > Buildout > VirtualEnv(2.4) > Package(zc.buildout==1.7.0)
Updating Py24 > Buildout
Updating Py25 > Buildout > File(work/py25/buildout.cfg) > \
Presence(work/py25/buildout.cfg)
Updating Py25 > Buildout > File(work/py25/buildout.cfg) > \
Content(work/py25/buildout.cfg)
Updating Py25 > Buildout > VirtualEnv(2.5) > VirtualEnvPy2_5 > \
VirtualEnvDownload(1.9.1) > Download(http://pypi.gocept.com/packages/\
source/v/virtualenv/virtualenv-1.9.1.tar.gz)
Updating Py25 > Buildout > VirtualEnv(2.5) > VirtualEnvPy2_5 > \
VirtualEnvDownload(1.9.1) > Extract(virtualenv-1.9.1.tar.gz) > \
Untar(virtualenv-1.9.1.tar.gz)
Updating Py25 > Buildout > VirtualEnv(2.5) > VirtualEnvPy2_5
Updating Py25 > Buildout > VirtualEnv(2.5) > Package(ssl==1.16)
Updating Py25 > Buildout > VirtualEnv(2.5) > Package(setuptools==1.3.2)
Updating Py25 > Buildout > VirtualEnv(2.5) > Package(zc.buildout==1.7.1)
Updating Py25 > Buildout
""".split("\n"))
    assert stderr == ""


@pytest.mark.slow
@pytest.mark.timeout(60)
def test_updates_old_distribute_to_setuptools(root):
    class Playground(Component):
        def configure(self):
            self.venv = VirtualEnv('2.7')
            self += self.venv

    playground = Playground()
    root.component += playground
    distribute = playground.venv.package(
        'distribute', version='0.6.34', timeout=10)
    playground.deploy()

    playground.venv.sub_components.remove(distribute)
    playground.venv.package('setuptools', version='0.9.8', timeout=10)
    playground.deploy()

    # We can't simply call verify, since distribute *still* manages to
    # manipulate the installation process and update itself, so our version
    # number is ignored and we get the most recent setuptools. *le major sigh*
    assert 'distribute-' not in playground.cmd(
        playground.workdir + '/bin/python -c '
        '"import setuptools; print setuptools.__file__"')[0]
