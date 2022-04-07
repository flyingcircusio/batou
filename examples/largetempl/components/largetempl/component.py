from batou.component import Component
from batou.lib.file import File


class LargeTemplate(Component):
    def configure(self):
        self += File("asdf", content="-" * (100 * 1024 + 1))
