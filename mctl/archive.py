import logging
import os
import sys
import time

from bz2     import BZ2File
from glob    import glob
from math    import floor
from tarfile import TarFile

log = logging.getLogger("mctl")

class Archive:
    def __init__(self, server_path, archive):
        if not server_path or not archive:
            return
        
        self.server_path  = server_path
        
        self.path         = archive['path']
        self.max_size     = archive['max-size']
        self.max_archives = archive['max-archives']
        self.paths        = archive['paths']
        
        if not os.path.isdir(self.path):
            try:
                os.makedirs(self.path)
            except os.error, msg:
                log.error("Unable to create path: %s: %s", self.path, msg)
                return False
    
    def all(self):        
        for path in self.paths:
            self.__path(path)
    
    def oversized(self):
        if not self.max_size:
            return
        
        for path in self.paths:
            spath = os.path.join(self.server_path, path)
            
            if not os.path.isfile(spath):
                continue
            
            self.__path(path, False)
    
    def __path(self, path, check_archives = True):
        spath = os.path.join(self.server_path, path)
        
        if not os.path.exists(spath):
            log.error("Path does not exist: %s" % (spath))
            return
        
        if os.path.isfile(spath):
            if not self.__check_max_size(spath):
                return
            
            ext = "bz2"
        else:
            ext = "tar.bz2"
        
        name  = os.path.basename(path)
        apath = os.path.join(self.path, "%s.\d+.%s" % (name, ext))
        
        if check_archives:
            self.__check_max_archives(apath)
        
        if not os.path.isdir(self.path):
            try:
                os.makedirs(self.path)
            except os.error, msg:
                log.error("Unable to create path: %s: %s", self.path, msg)
                return
        
        apath = "%s.%d.%s" % (name, time.time(), ext)
        apath = os.path.join(self.path, apath)
        
        if os.path.isfile(spath):
            res = self.__compress_file(path, apath)
        else:
            res = self.__compress_dir(path, apath)
        
        if self.max_size >= 1:
            os.remove(spath)
        
        if res:
            log.info("Archived: %s" % (spath))
        else:
            log.error("Unable to archive: %s" % (spath))
    
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
            try:
                os.remove(archive)
            except OSError, msg:
                log.error("Unable to remove: %s: %s", archive, msg)
    
    def __compress_file(self, path, apath):
        fpath = os.path.join(self.server_path, path)
        
        if not os.path.isfile(fpath):
            self.log.error("File not found: %s", (fpath))
            return False
        
        try:
            fp = open(fpath, "r")
        except IOError, msg:
            log.error("Unable to open: %s: %s", fpath, msg)
            return False
        
        try:
            bzf = BZ2File(apath, "w")
        except:
            log.error("Unable to open: %s", apath)
            return False
        
        fsize = os.path.getsize(fpath)
        l     = 0
        
        while True:
            data = fp.read(1024)
            
            if not data:
                break
            
            bzf.write(data)
            
            if log.level != logging.INFO:
                continue
            
            p = (float(fp.tell()) / float(fsize)) * 100
            p = int(floor(p))
            
            if l == p:
                continue
            
            sys.stdout.write("\033[2K")
            sys.stdout.write("Compressing(%d%%): %s\r" % (p, path))
            sys.stdout.flush()
            l = p
        
        fp.close()
        bzf.close()
        
        log.info("Compressed: %s" % (path))
        return True
    
    def __compress_dir(self, path, apath):
        try:
            tf = TarFile.open(apath, "w:bz2")
        except Exception, msg:
            log.error("Unable to open: %s: %s", apath, msg)
            return False
        
        log.info("Compressing: %s" % (path))
        
        cwd = os.getcwd()
        os.chdir(self.server_path)
        
        tf.add(path)
        tf.close()
        
        os.chdir(cwd)
        
        log.info("Compressed: %s" % (path))
        return True
