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

import base64
import favicons
import json
import logging
import os
import socket
import string
import struct
import sys
import util

from asyncore import dispatcher
from signal   import SIGINT
from socket   import SHUT_WR

log = logging.getLogger("mctl")

class FakeChannel(dispatcher):
    def __init__(self, sock, ping, kick):
        self.sock = sock
        self.ping = ping
        self.kick = kick

        self.version = 0
        dispatcher.__init__(self, sock)

    def close(self):
        self.sock.shutdown(SHUT_WR)
        dispatcher.close(self)

    def recv(self):
        size = util.varint_unpack_sock(self.sock)
        data = str()
        read = 0

        while read < size:
            try:
                data += self.sock.recv(size - read)
            except:
                return data

            read = len(data)

        return data

    def send(self, *args):
        data = self.pack(*args)
        size = len(data)
        sent = 0

        while sent < size:
            sent += self.sock.send(data[sent:])

    def pack(self, *args):
        data = str()

        for arg in args:
            data += arg if not isinstance(arg, int) else chr(arg)

        size = len(data)
        data = util.varint_pack(size) + data

        return data

    def handle_read(self):
        addr, port = self.addr
        data = self.recv()
        size = len(data)

        if size < 1:
            self.close()
            return

        pid = ord(data[0])

        if self.version == 0:
            if pid == 0x00:
                self.version = ord(data[1])
                return

            self.close()
            return

        if pid != 0x00:
            if pid == 0x01:
                self.send(data)
                return

            self.close()
            return

        if size == 1:
            ping = dict(self.ping)
            ping['version']['protocol'] = self.version

            jd = json.dumps(ping).encode("utf8")
            jd = self.pack(jd)

            self.send(0x00, jd)
            return

        data, nize = util.varint_unpack(data[1:])
        name = data[:nize].decode("utf8")

        jd = json.dumps(self.kick).encode("utf8")
        jd = self.pack(jd)

        log.info("%s[%s:%d] connected", name, addr, port)
        self.send(0x00, jd)

    def handle_close(self):
        self.close()

class FakeServer(dispatcher):
    def __init__(self, addr = None, port = 25565, favicon = None, motd = None,
                 message = None):
        addr    = addr    if addr    else "0.0.0.0"
        port    = port    if port    else 25565
        motd    = motd    if motd    else "Server Offline"
        message = message if message else "The server is currently offline"

        port = int(port)

        self.ping = {
            "version": {
                "name": "Minecraft!",
                "protocol": 0
            },

            "players": {
                "max": 0,
                "online": 0
            },

            "description": motd
        }

        self.kick = {
            "text": message
        }

        if favicon:
            fp = util.fopen(favicon, "r")

            if fp:
                data = fp.read()
                data = base64.b64encode(data)

                self.ping['favicon'] = "data:image/png;base64," + data
                fp.close()

        if not "favicon" in self.ping.keys():
            self.ping['favicon'] = "data:image/png;base64," + favicons.default

        dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.bind((addr, port))
            self.listen(5)
        except Exception, msg:
            log.critical("Failed to listen on %s:%d: %s", addr, port, msg)
            self.close()
            return

        log.info("Fake server started on %s:%d", addr, port)

    def handle_accept(self):
        sock = self.accept()
        FakeChannel(sock[0], self.ping, self.kick)

    def handle_close(self):
        self.close()

    @staticmethod
    def fork(server, addr = None, port = None, favicon = None, motd = None,
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

        if favicon:
            args.append("--favicon='%s'" % (favicon))

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
