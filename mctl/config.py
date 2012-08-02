import json
import logging
import os

from util import fopen

log = logging.getLogger("mctl")

def _merge_dicts(dict1, dict2):
    if not dict1 or not dict2:
        return

    for attr in dict1:
        if attr in dict2:
            dict1[attr] = dict2[attr]

    return dict1

class Versions:
    def __init__(self):
        self.__versions = dict()

        self.__path = os.path.join("~", ".mctl", "versions.json")
        self.__path = os.path.expanduser(self.__path)

    def load(self):
        if not os.path.isfile(self.__path):
            return False

        fp = fopen(self.__path, "r")

        if not fp:
            return False

        self.__versions = json.load(fp)
        fp.close()

        if not isinstance(self.__versions, dict):
            self.__versions = dict()

        return True

    def save(self):
        fp = fopen(self.__path, "w", True)

        if not fp:
            return False

        json.dump(self.__versions, fp, indent = True)
        fp.close()

        return True

    def get(self, server, package):
        if not server in self.__versions:
            return None

        if not package in self.__versions[server]:
            return None

        return self.__versions[server][package]

    def set(self, server, package, version):
        if not server in self.__versions:
            self.__versions[server] = dict()

        self.__versions[server][package] = version


class Config:
    def __init__(self, path = None):
        self.__path   = path
        self.__config = {
            'servers' : dict(),
            'packages': dict()
        }

        self.versions = Versions()

        if path:
            return

        path        = os.path.join("~", ".mctl", "config.json")
        self.__path = os.path.expanduser(path)

    def load(self):
        if not os.path.isfile(self.__path):
            return False

        fp = fopen(self.__path, "r")

        if not fp:
            return False

        self.__config = json.load(fp)
        fp.close()

        if not 'servers' in self.__config:
            self.__config['servers'] = dict()

        if not 'packages' in self.__config:
            self.__config['packages'] = dict()

        self.versions.load()

        return True

    def save(self):
        fp = fopen(self.__path, "w", True)

        if not fp:
            return False

        json.dump(self.__config, fp, indent = True)
        fp.close()

        self.versions.save()

        return True

    def servers_get(self):
        servers = dict()

        for name in self.__config['servers']:
            server = self.__config['servers'][name]
            server = _merge_dicts(self.server_new(), server)

            servers[name] = server

        return servers

    def packages_get(self):
        packages = dict()

        for name in self.__config['packages']:
            package = self.__config['packages'][name]
            package = _merge_dicts(self.package_new(), package)

            packages[name] = package

        return packages

    def archive_new(self):
        archive = {
            'path'        : None,
            'max-size'    : 0,
            'max-archives': 0,
            'paths'       : list()
        }

        return archive

    def server_new(self):
        server = {
            'path'    : None,
            'launch'  : None,
            'timeout' : 0,
            'archives': dict(),
            'packages': list()
        }

        return server

    def server_exists(self, server):
        if not server:
            return False

        return server in self.__config['servers']

    def server_get(self, server):
        if not server:
            return self.server_new()

        if not self.__config:
            return self.server_new()

        if not server in self.__config['servers']:
            return self.server_new()

        srv = self.__config['servers'][server]
        srv = _merge_dicts(self.server_new(), srv)

        for archive in srv['archives']:
            srv['archives'][archive] = _merge_dicts(self.archive_new(),
                                                    srv['archives'][archive])

        return srv

    def server_set(self, name, server):
        if not name or not server:
            return

        if not self.__config:
            return

        srv = _merge_dicts(self.server_new(), server)

        for archive in srv['archives']:
            srv['archives'][archive] = _merge_dicts(self.archive_new(),
                                                    srv['archives'][archive])

        self.__config['servers'][name] = srv

    def server_remove(self, server):
        if not name:
            return

        if not self.__config:
            return

        if server in self.__config['servers']:
            del self.__config['servers'][server]

    def package_new(self):
        package = {
            'path'   : None,
            'type'   : None,
            'url'    : None,
            'updater': None,
            'extract': list()
        }

        return package

    def package_exists(self, server):
        if not server:
            return False

        return server in self.__config['packages']

    def package_get(self, package):
        if not package:
            return self.package_new()

        if not self.__config:
            return self.package_new()

        if not package in self.__config['packages']:
            return self.package_new()

        pkg = self.__config['packages'][package]
        pkg = _merge_dicts(self.package_new(), pkg)

        return pkg

    def package_set(self, name, package):
        if not name or not package:
            return

        if not self.__config:
            return

        pkg = _merge_dicts(self.package_new(), package)
        self.__config['packages'][name] = pkg

    def package_remove(self, package):
        if not package:
            return

        if not self.__config:
            return

        if package in self.__config['packages']:
            del self.__config['packages'][package]
