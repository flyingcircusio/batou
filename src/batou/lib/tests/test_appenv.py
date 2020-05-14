from batou.lib.appenv import AppEnv, Requirements
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


def test_requirements_component(root):
    with open('requirements.txt', 'w') as f:
        f.write("""\
six==1.14.0
requests
-e/tmp/mypackage
-egit+https://github.com/flyingcircus/batou
mypackage[test]==0.0.1dev0
""")

    root.component += Requirements('requirements.lock')
    root.component.deploy()

    assert [
        '# Created by batou. Do not edit manually.',
        '-e/tmp/mypackage',
        '-egit+https://github.com/flyingcircus/batou',
        'mypackage[test]==0.0.1dev0',
        'requests',
        'six==1.14.0'] == open('requirements.lock', 'r').read().splitlines()

    root.component += Requirements(
        'requirements.lock',
        extra_index_urls=['https://pypi.example.com'],
        find_links=['https://download.example.com'],
        pinnings={'requests': '1.0', 'mypackage': '0.2'},
        editable_packages={'six': '/usr/dev/six'},
        additional_requirements=['pytest', 'pytest-flake8'])
    root.component.deploy()

    assert [
        '# Created by batou. Do not edit manually.',
        '-f https://download.example.com',
        '--extra-index-url https://pypi.example.com',
        '-e/tmp/mypackage',
        '-e/usr/dev/six',
        '-egit+https://github.com/flyingcircus/batou',
        'mypackage[test]==0.2',
        'pytest',
        'pytest-flake8',
        'requests==1.0'] == open('requirements.lock', 'r').read().splitlines()
