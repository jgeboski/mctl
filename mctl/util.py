import logging
import os
import sys
import urllib2
import urlparse

from math import floor

log = logging.getLogger("mctl")

def mkdir(path):
    if os.path.isdir(path):
        return True
    
    try:
        os.makedirs(path)
    except OSError, msg:
        log.error("Failed to make directory: %s: %s", path, msg)
        return False
    
    return True

def fopen(path, mode = "r", create_path = False):
    if create_path:
        dpath = os.path.dirname(path)
        
        if not mkdir(dpath):
            return None
    
    try:
        fp = open(path, mode)
    except IOError, msg:
        log.error("Failed to open: %s: %s", path, msg)
        fp = None
    
    return fp

def unlink(path):
    try:
        os.remove(path)
    except OSError, msg:
        log.error("Failed to remove: %s: %s", archive, msg)
        return False
    
    return True

def download(url, path):
    if not url or not path:
        return False
    
    try:
        ul = urllib2.urlopen(url)
    except urllib2.URLError, msg:
        log.error("Failed to download: %s: %s", url, msg)
        return False
    
    size = int(ul.info().getheader('Content-Length'))
    
    if size < 1:
        log.info("Failed to download: %s: nothing to download", url)
        return False
    
    fp = fopen(path, "w", True)
    
    if not fp:
        ul.close()
        return False
    
    f = os.path.basename(url)
    l = 0
    
    while True:
        data = ul.read(1024)
        
        if not data:
            break
        
        fp.write(data)
        
        if log.level != logging.INFO:
            continue
        
        p = (float(fp.tell()) / float(size)) * 100
        p = int(floor(p))
        
        if l == p:
            continue
        
        sys.stdout.write("\033[2K")
        sys.stdout.write("Downloading(%d%%): %s\r" % (p, f))
        sys.stdout.flush()
        l = p
    
    ul.close()
    fp.close()
    
    log.info("Downloaded: %s", f)
    return True

def url_get(url):
    if not url:
        return None
    
    headers = {
        "Accept-Language": "en-US"
    }
    
    try:
        rq = urllib2.Request(url, None, headers)
        ul = urllib2.urlopen(rq)
    except urllib2.URLError, msg:
        log.error("Failed to open: %s: %s", url, msg)
        return None
    
    data = ul.read()
    
    ul.close()
    return data

def url_join(base, url):
    if not base:
        return url
    
    if not url:
        return base
    
    if base[-1] != "/":
        base += "/"
    
    return urlparse.urljoin(base, url)
