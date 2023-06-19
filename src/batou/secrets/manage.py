import sys

from configupdater import ConfigUpdater

from batou import AgeCallError, GPGCallError
from batou.environment import Environment


class UnknownEnvironmentError(ValueError):
    """There is/are no environment(s) for this name(s)."""

    def __init__(self, names: list):
        self.names = names

    def __str__(self):
        return f'Unknown environment(s): {", ".join(self.names)}'


def summary():
    return_code = None
    environments = Environment.all()
    for environment in environments:
        print(environment.name)
        try:
            environment.load_secrets()
            environment.secret_provider.summary()
        except GPGCallError as e:
            print(e, file=sys.stderr)
            print(e.output, file=sys.stderr)
            return_code = 1
        except AgeCallError as e:
            print(e, file=sys.stderr)
            print(e.output, file=sys.stderr)
            return_code = 1
    return return_code


def add_user(keyid, environments, **kw):
    """Add a user to given environments.

    If environments is not given, a user is added
    to all environments.

    """
    environments_ = Environment.filter(environments)
    for environment in environments_:
        environment.load_secrets()
        with environment.secret_provider.edit():
            config = environment.secret_provider.config
            members = environment.secret_provider._get_recipients()
            if keyid not in members:
                members.append(keyid)
            config.set("batou", "members", ",\n".join(members).split("\n"))
            environment.secret_provider.write_config(
                str(config).encode("utf-8")
            )
    if not environments:
        raise UnknownEnvironmentError(
            [e.strip() for e in environments.split(",")]
        )


def remove_user(keyid, environments, **kw):
    """Remove a user from a given environment.

    If environments is not given, the user is removed
    from all environments.

    """
    environments_ = Environment.filter(environments)
    for environment in environments_:
        environment.load_secrets()
        with environment.secret_provider.edit():
            config = environment.secret_provider.config
            members = environment.secret_provider._get_recipients()
            if keyid in members:
                members.remove(keyid)
            config.set("batou", "members", ",\n".join(members).split("\n"))
            environment.secret_provider.write_config(
                str(config).encode("utf-8")
            )
    if not environments:
        raise UnknownEnvironmentError(
            [e.strip() for e in environments.split(",")]
        )
