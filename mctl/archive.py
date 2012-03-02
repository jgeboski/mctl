import logging
import os
import sys
import time

from bz2     import BZ2File
from glob    import glob
from math    import floor
from tarfile import TarFile
from util    import fopen, mkdir, unlink

log = logging.getLogger("mctl")

class Archive:
    def __init__(self, name, archive, server_path):
        if not server_path or not archive:
            return
        
        self.archive      = name
        self.path         = archive['path']
        self.max_size     = archive['max-size']
        self.max_archives = archive['max-archives']
        self.paths        = archive['paths']
        self.server_path  = server_path
    
    def all(self):
        c = 0
        
        for path in self.paths:
            if self.__path(path):
                c += 1
        
        log.info("%s: archived: %d of %d paths",
            self.archive, c, len(self.paths))
    
    def oversized(self):
        c = 0
        
        if not self.max_size:
            return
        
        for path in self.paths:
            spath = os.path.join(self.server_path, path)
            
            if not os.path.isfile(spath):
                continue
            
            if self.__path(path, False):
                c += 1
        
        log.info("%s: archived: %d of %d oversized paths",
            self.archive, c, len(self.paths))
    
    def __path(self, path, check_archives = True):
        spath = os.path.join(self.server_path, path)
        
        if not os.path.exists(spath):
            log.error("%s: path archiving failed: nonexistent path: %s",
                self.archive, spath)
            return False
        
        if os.path.isfile(spath):
            if not self.__check_max_size(spath):
                return False
            
            ext = "bz2"
        else:
            ext = "tar.bz2"
        
        mkdir(self.path)
        
        name  = os.path.basename(path)
        apath = os.path.join(self.path, "%s.\d+.%s" % (name, ext))
        
        if check_archives:
            self.__check_max_archives(apath)
        
        apath = "%s.%d.%s" % (name, time.time(), ext)
        apath = os.path.join(self.path, apath)
        
        if os.path.isfile(spath):
            res = self.__compress_file(path, apath)
        else:
            res = self.__compress_dir(path, apath)
        
        if self.max_size >= 1:
            unlink(spath)
        
        if res:
            log.info("%s: path archived: %s", self.archive, spath)
        else:
            log.error("%s: path archiving failed: %s", self.archive, spath)
        
        return True
    
    def __check_max_size(self, path):
        if self.max_size < 1:
            return True
        
        size = os.path.getsize(path)
        
        if size > (self.max_size * (1024 ** 2)):
            return True
        
        return False
    
    def __check_max_archives(self, path):
        if self.max_archives < 1:
            return
        
        files = glob(path)
        size  = len(files)
        
        if size < self.max_archives:
            return
        
        files = reversed(files.sort())
        size  = size - self.max_archives
        
        for archive in range(size):
            unlink(archive)
    
    def __compress_file(self, path, apath):
        fp = fopen(path, "r")
        
        if not fp:
            return False
        
        try:
            bzf = BZ2File(apath, "w")
        except:
            log.error("Failed to open: %s", apath)
            return False
        
        size = os.path.getsize(path)
        l    = 0
        
        while True:
            data = fp.read(1024)
            
            if not data:
                break
            
            bzf.write(data)
            
            if log.level != logging.INFO:
                continue
            
            p = (float(fp.tell()) / float(size)) * 100
            p = int(floor(p))
            
            if l == p:
                continue
            
            sys.stdout.write("\033[2K")
            sys.stdout.write("Compressing(%d%%): %s\r" % (p, path))
            sys.stdout.flush()
            l = p
        
        fp.close()
        bzf.close()
        
        return True
    
    def __compress_dir(self, path, apath):
        try:
            tf = TarFile.open(apath, "w:bz2")
        except Exception, msg:
            log.error("Failed to open: %s: %s", apath, msg)
            return False
        
        log.info("Compressing: %s", path)
        
        cwd = os.getcwd()
        os.chdir(self.server_path)
        
        tf.add(path)
        tf.close()
        os.chdir(cwd)
        
        return True
