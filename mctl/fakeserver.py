#
# Copyright 2012-2013 James Geboski <jgeboski@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import os
import socket
import string
import struct
import sys
import util

from asyncore    import dispatcher
from collections import OrderedDict
from signal      import SIGINT

log = logging.getLogger("mctl")

mcclients = OrderedDict([
    (61, "1.5.2"),
    (60, "1.5.1"),
    (51, "1.4.7"),
    (49, "1.4.4"),
    (47, "1.4.2"),
    (39, "1.3.2")
])

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
        ver        = ord(data[1])

        #print "Version: %s" % (ver)

        if ver in mcclients:
            l, = struct.unpack(">h", data[2:4])
            l  = (l * 2) + 4

            user   = data[4:l].decode("UTF-16BE")
            client = mcclients[ver]
        else:
            user   = "Unknown"
            client = "Unknown"

        log.info("%s[%s:%d] connected (MC: %s)", user, addr, port, client)
        self.send(self.__kick)

    def handle_close(self):
        self.close()

class FakeServer(dispatcher):
    def __init__(self, addr = None, port = 25565, version = None, motd = None,
                 message = None):
        addr    = addr    if addr    else "0.0.0.0"
        port    = port    if port    else 25565
        motd    = motd    if motd    else "Server Offline"
        message = message if message else "The server is currently offline"

        if version and not isinstance(version, int):
            version = int(version)

        if not version in mcclients.keys():
            version = mcclients.keys()[0]

        mcpver = str(version);
        mcsver = mcclients[version];

        port = int(port)
        zero = str(0).encode("UTF-16BE")
        mlen = len(mcpver) + len(mcsver) + len(motd) + (len(zero) * 2) + 5

        self.__ping = string.join((
            "\xFF",
            struct.pack(">h", mlen),
            "\x00\xA7\x00\x31",
            "\x00\x00", mcpver.encode("UTF-16BE"),
            "\x00\x00", mcsver.encode("UTF-16BE"),
            "\x00\x00", motd.encode("UTF-16BE"),
            "\x00\x00", zero,
            "\x00\x00", zero
        ), '')

        mlen = len(message)

        self.__kick = string.join((
            "\xFF",
            struct.pack(">h", mlen),
            message.encode("UTF-16BE")
        ), '')

        dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.bind((addr, port))
            self.listen(5)
        except Exception, msg:
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
    def fork(server, addr = None, port = None, version = None, motd = None,
             message = None):
        if not server:
            return

        args = list()

        args.append("--foreground")
        args.append("--server=%s" % (server))

        if addr:
            args.append("--addr=%s" % (addr))

        if port:
            args.append("--port=%s" % (port))

        if version:
            args.append("--version=%s" % (version))

        if motd:
            args.append("--motd='%s'" % (motd))

        if message:
            args.append("--message='%s'" % (message))

        name = "fake-%s" % (server)
        cmd  = "%s %s" % (sys.argv[0], string.join(args))

        log.info("%s: fake server starting...", server)
        util.screen_new(name, cmd)

    @staticmethod
    def pidfile(server):
        path = os.path.join("~", ".mctl", "run", "fake-%s.pid" % (server))
        path = os.path.expanduser(path)

        return path

    @staticmethod
    def running(server):
        pidfile = FakeServer.pidfile(server)

        if not os.path.isfile(pidfile):
            return False

        fp = util.fopen(pidfile, "r")

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
        except:
            return False

        return True

    @staticmethod
    def kill(server):
        log.info("%s: fake server stopping...", server)

        pidfile = FakeServer.pidfile(server)
        fp      = util.fopen(pidfile, "r")

        if not fp:
            return False

        try:
            pid = int(fp.read())
        except:
            pid = 0

        fp.close()
        util.unlink(pidfile)

        if not pid:
            return False

        try:
            os.kill(pid, SIGINT)
        except Exception, msg:
            log.error("Failed to kill process (%d): %s", pid, msg)
            return False

        return True
