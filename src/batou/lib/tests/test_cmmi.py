

def test_build_breadcrumb_shortens_url():
    from batou.lib.cmmi import Build

    b = Build('http://launchpad.net/libmemcached/1.0/0.46/'
              '+download/libmemcached-0.46.tar.gz')
    assert b._breadcrumb == 'Build(libmemcached-0.46.tar.gz)'
