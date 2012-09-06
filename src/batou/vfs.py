import os.path


class Developer(object):

    def __init__(self, environment, config):
        self.environment = environment

    def map(self, path):
        if path.startswith(self.environment.workdir_base):
            return path
        path = path[1:]
        path = os.path.join(self.environment.workdir_base, '_', path)
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(path)
        return path


class Map(object):

    def __init__(self, environment, config):
        self.map = []
        for key, value in config.items():
            if not key.startswith('/'):
                continue
            self.map.append((key, value))
        self.map.sort(key=lambda x: len(x[0]), reverse=True)

    def map(self, path):
        for prefix, replacement in self.map:
            if path.startswith(prefix):
                return path.replace(prefix, replacement, 1)
        return path
