from batou.lib.cmmi import Build, Configure
import mock


def test_build_breadcrumb_shortens_url():
    b = Build('http://launchpad.net/libmemcached/1.0/0.46/'
              '+download/libmemcached-0.46.tar.gz')
    assert b._breadcrumb == 'Build(libmemcached-0.46.tar.gz)'


def test_configure_defaults_prefix_to_workdir(root):
    configure = Configure('.')
    configure.cmd = mock.Mock()
    root.component += configure
    assert configure.prefix == root.component.workdir
    root.component.deploy()
    assert (
        ' --prefix={}'.format(root.component.workdir) in
        configure.cmd.call_args[0][0])


def test_configure_accepts_custom_prefix(root):
    configure = Configure('.', prefix='/asdf')
    configure.cmd = mock.Mock()
    root.component += configure
    assert configure.prefix == '/asdf'
    root.component.deploy()
    assert ' --prefix=/asdf' in configure.cmd.call_args[0][0]
