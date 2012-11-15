import logging
import os
import time
import util

from package import Package

log = logging.getLogger("mctl")

class Server:
    def __init__(self, name, server):
        self.server   = name
        self.path     = server['path']
        self.launch   = server['launch']
        self.timeout  = server['timeout']
        self.archives = server['archives']
        self.packages = server['packages']

        self.screen_name = "mctl-%s" % (name)

    def _archive(self):
        for archive in self.archives:
            path = os.path.join(self.path, archive['file'])

            try:
                size = os.path.getsize(path)
            except:
                continue

            if size < (archive['size'] * (1024 ** 2)):
                continue

            apath = os.path.basename(path)
            apath = "%s.%d.bz2" % (apath, time.time())
            apath = os.path.join(archive['path'], apath)

            util.mkdir(archive['path'])
            util.compress_file_bz2(path, apath)
            util.unlink(path)

    def command(self, command):
        util.screen_command_send(self.screen_name, command)

    def upgrade(self, config, force = False, packages = None,
                exclude = None, dryrun = False):
        if packages:
            if isinstance(packages, str):
                packages = packages.split(",")
            elif not isinstance(packages, list):
                packages = self.packages
        else:
            packages = self.packages

        if exclude:
            if isinstance(exclude, str):
                exclude = exclude.split(",")
            elif not isinstance(exclude, list):
                exclude = list()

            for e in exclude:
                try:
                    packages.remove(e)
                except ValueError:
                    pass

        for package in packages:
            if not config.package_exists(package):
                log.error("%s: package upgrade failed: invalid package",
                    package)
                return

            cpkg = config.package_get(package)
            pkg  = Package(package, cpkg, self.path, dryrun)

            version = config.versions.get(self.server, package)
            version = pkg.upgrade(version, force)

            config.versions.set(self.server, package, version)

        if not dryrun:
            config.versions.save()

        return config

    def start(self, force = False):
        cwd = os.getcwd()

        if util.screen_exists(self.screen_name):
            log.error("%s: failed to start: server is running", self.server)
            return

        self._archive()
        log.info("%s: server starting...", self.server)

        os.chdir(self.path)
        util.screen_new(self.screen_name, self.launch)
        os.chdir(cwd)

    def stop(self, message = None):
        if not util.screen_exists(self.screen_name):
            log.error("%s: failed to stop: server is not running", self.server)
            return

        log.info("%s: server stopping...", self.server)

        if message:
            self.command('say %s' % (message))

        s = self.timeout

        if s:
            while s >= 1:
                self.command("say Server stopping in %s second(s)" % (s))
                log.info("%s: server stopping: T minus %s seconds(s)",
                    self.server, s)

                s -= 10
                time.sleep(10)

        self.command("save-all")
        self.command("stop")

        util.screen_join(self.screen_name)
