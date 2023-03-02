from batou.environment import Environment


def summary():
    environments = Environment.all()
    for environment in environments:
        print(environment.name)
        environment.secret_provider.summary()


def add_user():
    pass


def remove_user():
    pass
