from configupdater import ConfigUpdater

from batou.environment import Environment


def summary():
    environments = Environment.all()
    for environment in environments:
        print(environment.name)
        environment.secret_provider.summary()


def add_user(keyid, environments, **kw):
    """Add a user to given environments.

    If environments is not given, a user is added
    to all environments.

    """
    for environment in Environment.filter(environments):
        with environment.secret_provider.edit():
            config = environment.secret_provider.config
            members = environment.secret_provider._get_recipients()
            if keyid not in members:
                members.append(keyid)
            config.set("batou", "members", ",\n".join(members).split("\n"))
            environment.secret_provider.write_config(
                str(config).encode("utf-8")
            )


def remove_user(keyid, environments, **kw):
    """Remove a user from a given environment.

    If environments is not given, the user is removed
    from all environments.

    """
    for environment in Environment.filter(environments):
        with environment.secret_provider.edit():
            config = environment.secret_provider.config
            members = environment.secret_provider._get_recipients()
            if keyid in members:
                members.remove(keyid)
            config.set("batou", "members", ",\n".join(members).split("\n"))
            environment.secret_provider.write_config(
                str(config).encode("utf-8")
            )
