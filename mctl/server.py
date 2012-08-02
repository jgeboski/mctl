import logging
import os
import re
import shlex
import socket
import struct
import sys
import time

from archive    import Archive
from asyncore   import dispatcher
from package    import Package
from signal     import SIGINT
from subprocess import Popen, PIPE
from util       import fopen, unlink

log = logging.getLogger("mctl")

def _execute_command(command, quiet = True):
    args = shlex.split(str(command))

    if quiet:
        p = Popen(args, 0, None, PIPE, PIPE, PIPE)
    else:
        p = Popen(args)

    p.wait()
    return p.stdout.read() if quiet else None

def _screen_exists(name):
    ret   = _execute_command("screen -ls")
    match = re.search("^.*\d+\.%s.*$" % (name), ret, re.MULTILINE)

    if match:
        return True

    return False

def _screen_new(name, command):
    _execute_command("screen -S %s -dm %s" % (name, command))

def _screen_join(name):
    _execute_command("screen -S %s -x" % (name), False)

def _screen_command_send(name, command):
    _execute_command("screen -S %s -p 0 -X stuff '%s\n'" % (name, command))

class _FakeChannel(dispatcher):
    def __init__(self, sock, ping, kick):
        dispatcher.__init__(self, sock)

        self.__ping = ping
        self.__kick = kick

    def handle_read(self):
        data = self.recv(256)

        if len(data) < 1:
            return

        if data[0] == '\xFE':
            self.send(self.__ping)
            return

        if data[0] != '\x02':
            self.send(str())
            return

        addr, port = self.addr

        # For 1.2 - 1.3 compatibility
        data = data[4:].replace("\t", ";")
        data = data.split(";")[0]

        log.info("%s [%s:%d] attempted to join", data, addr, port)

        self.send(self.__kick)

    def handle_close(self):
        self.close()

class FakeServer(dispatcher):
    def __init__(self, addr = None, port = 25565, motd = None, message = None):
        addr    = addr    if addr    else "0.0.0.0"
        port    = port    if port    else 25565
        motd    = motd    if motd    else "Server Offline"
        message = message if message else "The server is currently offline"

        self.__ping = "\xFF%s%s%s" % (
            struct.pack(">h", (len(motd) + 4)),
            motd.encode("UTF-16BE"),
            "\x00\xA7\x00\x30\x00\xA7\x00\x30",
        )

        self.__kick = "\xFF%s%s" % (
            struct.pack(">h", len(message)),
            message.encode("UTF-16BE")
        )

        dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.bind((addr, port))
            self.listen(5)
        except socket.error, msg:
            self.close()

            log.critical("Failed to listen on %s:%d: %s", addr, port, msg)
            return

        log.info("Fake server started on %s:%d", addr, port)

    def handle_accept(self):
        pair = self.accept()

        if not pair:
            return

        sock, addr = pair

        _FakeChannel(sock, self.__ping, self.__kick)

    def handle_close(self):
        self.close()

    @staticmethod
    def pidfile(server):
        path = os.path.join("~", ".mctl", "run", "%s-fake.pid" % (server))
        path = os.path.expanduser(path)

        return path

    @staticmethod
    def running(server):
        pidfile = FakeServer.pidfile(server)

        if not os.path.isfile(pidfile):
            return False

        fp = fopen(pidfile, "r")

        if not fp:
            return False

        try:
            pid = int(fp.read())
        except:
            pid = 0

        fp.close()

        if not pid:
            return False

        try:
            os.kill(pid, 0)
        except OSError, msg:
            return False

        return True

    @staticmethod
    def kill(server):
        pidfile = FakeServer.pidfile(server)
        fp      = fopen(pidfile, "r")

        if not fp:
            return False

        try:
            pid = int(fp.read())
        except:
            pid = 0

        fp.close()
        unlink(pidfile)

        if not pid:
            return False

        try:
            os.kill(pid, SIGINT)
        except OSError, msg:
            log.error("Failed to kill process (%d): %s", pid, msg)
            return False

        return True

def PFakeServer(server, addr = None, port = 25565, motd = None, message = None):
    if not server:
        return

    addr    = addr      if addr    else "0.0.0.0"
    port    = int(port) if port    else 25565
    motd    = motd      if motd    else "Server Offline"
    message = message   if message else "The server is currently offline"

    name = "mctl-fake-%s" % (server)
    cmd  = "%s --server=%s --addr=%s --port=%d --motd='%s' --message='%s'" % (
        "mctl-fake", server, addr, port, motd, message
    )

    _screen_new(name, cmd)

class Server:
    def __init__(self, name, server):
        self.server   = name
        self.path     = server['path']
        self.launch   = server['launch']
        self.timeout  = server['timeout']
        self.archives = server['archives']
        self.packages = server['packages']

        self.screen_name = "mctl-%s" % (name)

    def command(self, command):
        _screen_command_send(self.screen_name, command)

    def archive(self, archives = None, exclude = None):
        if archives:
            if isinstance(archives, str):
                archives = archives.split(",")
            elif not isinstance(archives, list):
                archives = self.archives.keys()
        else:
            archives = self.archives.keys()

        if exclude:
            if isinstance(exclude, str):
                exclude = exclude.split(",")
            elif not isinstance(exclude, list):
                exclude = list()

            for e in exclude:
                try:
                    archives.remove(e)
                except ValueError:
                    pass

        for archive in archives:
            archive = Archive(archive, self.archives[archive], self.path)
            archive.all()

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

        if FakeServer.running(self.server):
            if force:
                self.stop_fake()
            else:
                log.error("%s: failed to start: fake server is running",
                    self.server)
                return

        if _screen_exists(self.screen_name):
            log.error("%s: failed to start: server is running", self.server)
            return

        for archive in self.archives:
            archive = Archive(archive, self.archives[archive], self.path)
            archive.oversized()

        log.info("%s: server starting...", self.server)

        os.chdir(self.path)
        _screen_new(self.screen_name, self.launch)
        os.chdir(cwd)

    def stop(self, message = None):
        if not _screen_exists(self.screen_name):
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

        _screen_join(self.screen_name)

    def fake_start(self, motd = None, message = None, force = False):
        if _screen_exists(self.screen_name):
            if force:
                self.stop(message)
            else:
                log.error("%s: failed to start fake: server is running",
                    self.server)
                return

        if FakeServer.running(self.server):
            log.error("%s: failed to start fake: fake server is running",
                self.server)
            return

        path = os.path.join(self.path, "server.properties")
        fp   = fopen(path, "r")

        if not fp:
            return

        data = fp.read()
        fp.close()

        match = re.search("^server-ip=(.*)$", data, re.MULTILINE)

        if not match:
            log.warning("Failed to get `server-ip' from: %s", path)
            return

        addr  = match.group(1)
        match = re.search("^server-port=(\d+)$", data, re.MULTILINE)

        if not match:
            log.warning("Failed to get `server-port' from: %s", path)
            return

        port = match.group(1)

        log.info("%s: fake server starting...", self.server)
        PFakeServer(self.server, addr, port, motd, message)

    def fake_stop(self):
        if not FakeServer.running(self.server):
            log.error("%s: failed to stop fake: fake server is not running",
                self.server)
            return

        log.info("%s: fake server stopping...", self.server)
        FakeServer.kill(self.server)
