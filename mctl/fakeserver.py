import logging
import socket
import struct

from socket import socket

log = logging.getLogger("fakeserver")

class FakeServer:
    def __init__(self, addr = None, port = 25565, motd = None, message = None):
        self.addr = addr if addr      else "0.0.0.0"
        self.port = port if port >= 1 else 25565
        
        self.__sock = None
        
        if not motd:
            motd = "Server Offline"
            
        if not message:
            message = "The server is currently offline"
        
        self.__ping_data = "\xFF%s%s%s" % (
            struct.pack(">h", (len(motd) + 4)),
            motd.encode("UTF-16BE"),
            "\x00\xA7\x00\x30\x00\xA7\x00\x30",
        )
        
        self.__kick_data = "\xFF%s%s" % (
            struct.pack(">h", len(message)),
            message.encode("UTF-16BE")
        )
    
    def start(self):
        if self.__sock:
            self.__sock.close()
        
        self.__sock = socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            self.__sock.bind((self.addr, self.port))
            self.__sock.listen(5)
        except socket.error, msg:
            self.__sock.close()
            self.__sock = None
            
            log.critical("Unable to start fake server: %s", msg)
            return
        
        log.info("Fake server started on %s:%d", self.addr, self.port)
    
    def handle_events(self, timeout = 2):
        if not self.__sock:
            return
        
        try:
            conn, addr = self.__sock.accept()
            conn.settimeout(timeout)
        except socket.error:
            return
        
        data = self.__recv(conn, addr, 256)
        
        if len(data) < 1:
            conn.close()
            return
        
        if data[0] == "\xFE":
            self.__send(conn, addr, self.__ping_data)
            conn.close()
            return
        
        log.info("%s [%s:%s] attempted to join", data, addr[0], addr[1])
        
        self.__send(conn, addr, self.__kick_data)
        conn.close()
    
    def stop(self):
        if not self.__sock:
            return
        
        self.__sock.close()
    
    def __recv(self, conn, addr, size):
        try:
            data = conn.recv(size)
        except socket.error, msg:
            data = None
            log.error("Unable to read from %s:%s: %s", addr[0], addr[1], msg)
        
        return data
    
    def __send(self, conn, addr, data):
        try:
            sent = conn.send(data)
        except socket.error, msg:
            sent = 0
            log.error("Unable to write to %s:%s: %s", addr[0], addr[1], msg)
        
        return sent
