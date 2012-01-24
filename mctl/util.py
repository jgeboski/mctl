import logging
import sys
import urllib2
import urlparse

from math import floor

log = logging.getLogger("util")

def download(url, path):
    if not url or not path:
        return False
    
    try:
        ul = urllib2.urlopen(url)
    except urllib2.URLError, msg:
        log.error("Unable to download: %s: %s", url, msg)
        return False
    
    size = int(ul.info().getheader('Content-Length'))
    
    if size < 1:
        log.info("Nothing to download from: %s", url)
        return False
    
    try:
        of = open(path, "w")
    except IOError, msg:
        ul.close()
        
        log.error("Unable to open: %s: %s", path, msg)
        return False
    
    l = 0
    while True:
        data = ul.read(1024)
        
        if not data:
            break
        
        of.write(data)
        
        if log.level != logging.INFO:
            continue
        
        p = (float(of.tell()) / float(size)) * 100
        p = int(floor(p))
        
        if l == p:
            continue
        
        sys.stdout.write("\033[2K")
        sys.stdout.write("Downloading(%d%%): %s\r" % (p, url))
        sys.stdout.flush()
        l = p
    
    ul.close()
    of.close()
    
    log.info("Downloaded: %s", url)
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
        log.error("Unable to open: %s: %s", url, msg)
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
