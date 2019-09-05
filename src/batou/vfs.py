import os.path


class Developer(object):

    def __init__(self, environment, config):
        self.environment = environment

    def map(self, path):
        if path.startswith(self.environment.workdir_base):
            return path
        if not os.path.isabs(path):
            return path
        path = path[1:]
        path = os.path.join(self.environment.workdir_base, '_', path)
        dir = os.path.dirname(path)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return path


class Map(object):

    def __init__(self, environment, config):
        self._map = []
        for key, value in list(config.items()):
            if not key.startswith('/'):
                continue
            self._map.append((key, value))
        self._map.sort(key=lambda x: len(x[0]), reverse=True)

    def map(self, path):
        for prefix, replacement in self._map:
            if path.startswith(prefix):
                return path.replace(prefix, replacement, 1)
        return path
