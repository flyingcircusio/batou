from batou.component import Component
from batou.lib.python import VirtualEnv


def test_venv_updates_if_python_changes(root):
    import ast

    class Playground(Component):
        namevar = 'version'

        def configure(self):
            self.venv = VirtualEnv(self.version)
            self += self.venv

    playground = Playground('2.7')
    root.component += playground
    playground.deploy()
    root.component.sub_components.remove(playground)

    playground = Playground('3')
    root.component += playground
    playground.deploy()

    out, err = playground.cmd(
        '{}/bin/python -c "import sys; print(sys.version_info[:2])"'.format(
            playground.workdir))
    assert 3 == ast.literal_eval(out)[0]


def test_venv_does_not_update_if_python_does_not_change(root):

    class Playground(Component):
        namevar = 'version'

        def configure(self):
            self.venv = VirtualEnv(self.version)
            self += self.venv

    playground = Playground('2.7')
    root.component += playground
    playground.deploy()
    assert playground.changed
    playground.deploy()
    assert not playground.changed
