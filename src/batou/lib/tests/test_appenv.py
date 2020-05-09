from batou.lib.appenv import AppEnv
import os.path


def test_simple_appenv(root):
    with open('requirements.lock', 'w') as f:
        # I hate using a real package and a real index here ...
        f.write('six==1.14.0\n')

    appenv = AppEnv('3')
    root.component += appenv
    root.component.deploy()

    assert os.path.exists(os.path.join(root.component.workdir, 'bin'))
    assert os.path.exists(
        os.path.join(root.component.workdir, 'bin', 'python3'))
    assert os.path.exists(
        os.path.join(root.component.workdir, '.appenv', 'current'))

    hashes = os.listdir(os.path.join(root.component.workdir, '.appenv'))
    assert len(hashes) == 2

    # Running it twice doesn't change anything
    appenv.prepare(root.component)
    root.component.deploy()

    assert os.path.exists(os.path.join(root.component.workdir, 'bin'))
    assert os.path.exists(
        os.path.join(root.component.workdir, 'bin', 'python3'))
    assert os.path.exists(
        os.path.join(root.component.workdir, '.appenv', 'current'))

    hashes2 = os.listdir(os.path.join(root.component.workdir, '.appenv'))
    assert hashes2 == hashes
    assert len(hashes2) == 2
    # Changing the requirements does change something:L
    with open('requirements.lock', 'w') as f:
        # I hate using a real package and a real index here ...
        f.write('# comment\nsix==1.14.0\n')

    appenv.prepare(root.component)
    root.component.deploy()

    assert os.path.exists(os.path.join(root.component.workdir, 'bin'))
    assert os.path.exists(
        os.path.join(root.component.workdir, 'bin', 'python3'))
    assert os.path.exists(
        os.path.join(root.component.workdir, '.appenv', 'current'))

    hashes3 = os.listdir(os.path.join(root.component.workdir, '.appenv'))
    assert hashes3 != hashes

    assert len(hashes3) == 2
