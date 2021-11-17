import importlib
import os

from batou.migrate import output_migration_step as output

step_2301 = importlib.import_module('batou.migrate.migrations.2301')


def get_tree_structure(parent, indent=0):
    """Get the directory tree structure in a human readable format."""
    for child in sorted(parent.iterdir(), key=lambda x: x.name):
        yield f"{' ' * 2 * indent}{child.name}"
        if child.is_dir():
            yield from get_tree_structure(child, indent + 1)


def create(path, text):
    """Create a file and write text into it.

    Additionally creates immediate directories if needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_2301__migrate__1(tmp_path):
    """It moves environment files around."""
    os.chdir(tmp_path)
    create(tmp_path / 'components' / 'zope' / 'component.py', '')
    create(tmp_path / 'environments' / 'test.cfg', 'test')
    create(tmp_path / 'environments' / 'stag.cfg', 'stag')
    create(tmp_path / 'environments' / 'prod.cfg', 'prod')
    create(tmp_path / 'secrets' / 'stag.cfg', 'stag')
    create(tmp_path / 'secrets' / 'prod.cfg', 'prod')
    create(tmp_path / 'secrets' / 'prod-extrafile.bar', 'prod')
    create(tmp_path / 'work' / 'zope' / 'zope.conf', '')
    create(tmp_path / '.gitignore', '')
    create(tmp_path / 'appenv', '')
    (tmp_path / 'batou').symlink_to('appenv')
    create(tmp_path / 'requirements.lock', '')
    create(tmp_path / 'requirements.txt', '')
    assert [
        '.gitignore',
        'appenv',
        'batou',
        'components',
        '  zope',
        '    component.py',
        'environments',
        '  prod.cfg',
        '  stag.cfg',
        '  test.cfg',
        'requirements.lock',
        'requirements.txt',
        'secrets',
        '  prod-extrafile.bar',
        '  prod.cfg',
        '  stag.cfg',
        'work',
        '  zope',
        '    zope.conf', ] == list(get_tree_structure(tmp_path))
    step_2301.migrate(output)
    assert [
        '.gitignore',
        'appenv',
        'batou',
        'components',
        '  zope',
        '    component.py',
        'environments',
        '  prod',
        '    environment.cfg',
        '    extrafile.bar',
        '    secrets.cfg',
        '  stag',
        '    environment.cfg',
        '    secrets.cfg',
        '  test',
        '    environment.cfg',
        'requirements.lock',
        'requirements.txt',
        'secrets',
        'work',
        '  zope',
        '    zope.conf', ] == list(get_tree_structure(tmp_path))
    envs = tmp_path / 'environments'
    assert (envs / 'test' / 'environment.cfg').read_text() == 'test'
    assert (envs / 'prod' / 'environment.cfg').read_text() == 'prod'
    assert (envs / 'prod' / 'secrets.cfg').read_text() == 'prod'
    assert (envs / 'prod' / 'extrafile.bar').read_text() == 'prod'
