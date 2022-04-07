from batou.component import Component
from batou.lib.file import File


class Hello(Component):

    magic_word = None
    other_word = None

    def configure(self):
        self += File(
            "hello",
            content="The magic word is {{component.magic_word}}.\n"
            "The other word is {{component.other_word}}.\n",
        )

        self += File(
            "other-secrets.yaml",
            content=self.environment.secret_files["foobar.yaml"],
        )
