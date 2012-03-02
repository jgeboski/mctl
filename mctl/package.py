import json
import logging
import os
import re
import util

from util    import download, mkdir, unlink, url_get, url_join
from xml.dom import minidom
from zipfile import ZipFile

log = logging.getLogger("mctl")

def _xml_child_get(node, name):
    if not node.hasChildNodes():
        return None
    
    for node in node.childNodes:
        if node.nodeName == name:
            return node
    
    return None

class Package:
    def __init__(self, name, package, swd):
        self.package = name
        self.path    = package['path']
        self.type    = package['type']
        self.url     = package['url']
        self.updater = package['updater']
        self.extract = package['extract']
        
        if self.path:
            self.path = os.path.join(swd, self.path)
        else:
            self.path = swd
    
    def update(self, version, force = False):
        if not mkdir(self.path):
                return version
        
        if self.updater == "bukkitdev":
            uver, urlh = self.__bukkitdev_info()
        elif self.updater == "bukkitdl":
            uver, urlh = self.__bukkitdl_info()
        elif self.updater == "jenkins":
            uver, urlh = self.__jenkins_info()
        else:
            log.error("%s: package upgrade failed: invalid updater `%s'",
                      self.package, self.updater)
            
            return version
        
        if not urlh:
            log.error("%s: package upgrade failed", self.package)
            return version
        
        out = os.path.join(self.path, "%s.%s" % (
            self.package, self.type
        ))
        
        if uver and uver == version and not force:
            log.info("%s: package already up-to-date", self.package)
            return version
        
        if not download(urlh, out):
            return version
        
        log.info("%s: package upgraded: %s -> %s",
                 self.package, version, uver)
        
        if self.type != "zip":
            return uver
        
        if len(self.extract) < 1:
            return uver
        
        zf = ZipFile(out, "r")
        nl = zf.namelist()
        
        for path in self.extract:
            if not path.endswith("/") and path in nl:
                zf.extract(path, self.path)
                continue
            
            for zpath in nl:
                if zpath.endswith("/"):
                    continue
                
                if not zpath.startswith(path):
                    continue
                
                zf.extract(zpath, self.path)
        
        zf.close()
        unlink(out)
        
        return uver
    
    def __bukkitdev_info(self):
        urlh = url_join(self.url, "files.rss")
        data = url_get(urlh)
        
        if not data:
            return (None, None)
        
        dom  = minidom.parseString(data)
        root = _xml_child_get(dom.documentElement, "channel")
        
        if not root:
            return (None, None)
        
        item = _xml_child_get(root, "item")
        
        if not item:
            return (None, None)
        
        version = _xml_child_get(item, "title")
        version = version.firstChild.nodeValue.lower()
        
        # Clean up the version numbers
        version = version.replace("v", "")
        
        match = re.search("((?:\d+\.)(?:\w+\.)?(?:\w+\.)?(?:\w+))", version)
        
        if match:
            version = match.group(1)
        else:
            log.warning("%s: version extraction failed: reported version `%s'",
                        self.package, version)
            
            version = None
        
        urlh = _xml_child_get(item, "link")
        data = url_get(urlh.firstChild.nodeValue)
        
        if not data:
            return (version, None)
        
        match = re.search(
            "<a href=\"(\S*\.%s)\">Download</a>" % (self.type), data)
        
        if not match:
            return (version, None)
        
        return (version, match.group(1))
    
    def __bukkitdl_info(self):
        match = re.match(
            ".*dl.bukkit.org/downloads/(\w+)(/(?:list)/(\w+))?/?", self.url)
        
        if not match or not match.group(1):
            log.error("%s: URL parsing failed: invalid bukkitdl URL",
                self.package)
            return
        
        urlh = "http://dl.bukkit.org/api/1.0/downloads/" \
               "projects/%s/artifacts/" % (match.group(1))
        
        if match.group(3):
            urlh += "%s/" % (match.group(3))
        
        page = 1
        
        while True:
            data  = url_get("%s?page=%d" % (urlh, page))
            page += 1
            
            if not data:
                break
            
            data = json.loads(data)
            
            if (not 'pages' in data) or (data['pages'] < page):
                break
            
            if not 'results' in data:
                break
            
            for item in data['results']:
                if item['is_broken']:
                    continue
                
                return (item['build_number'], item['file']['url'])
        
        return (None, None)
    
    def __jenkins_info(self):
        urlh = url_join(self.url, "rssAll")
        data = url_get(urlh)
        
        if not data:
            return (None, None)
        
        dom  = minidom.parseString(data)
        root = dom.documentElement
        
        for entry in dom.getElementsByTagName("entry"):
            title = _xml_child_get(entry, "title")
            title = title.firstChild.nodeValue
            match = re.match(".* #(\d+).* \((.*)\)", title)
            
            if not match:
                continue
            
            version = match.group(1)
            state   = match.group(2).lower()
            
            if state != "stable" and state != "back to normal":
                continue
            
            urlh = _xml_child_get(entry, "link")
            urlh = urlh.getAttribute("href")
            data = url_get(urlh)
            
            if not data:
                continue
            
            match = re.search("\"(artifact/\S+\.%s)\"" % (self.type), data)
            
            if match:
                urlr = url_join(urlh, match.group(1))
                return (version, urlr)
            
            match = re.search("\"(\S+\$%s)/\"" % (self.package), data)
            
            if not match:
                continue
            
            urlh = url_join(urlh, match.group(1))
            data = url_get(urlh)
            
            if not data:
                continue
            
            match = re.search("\"(artifact/\S+\.%s)\"" % (self.type), data)
            
            if not match:
                log.warning("%s: failed to get download URL: (version: %s) "
                            "reverting to previous version",
                            self.package, version)
                continue
            
            urlr  = url_join(urlh, match.group(1))
            
            return (version, urlr)
        
        return (None, None)
