import logging
import os
import re
import util

from util    import download, url_get, url_join
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
        if not os.path.isdir(self.path):
            try:
                os.makedirs(self.path)
            except os.error, msg:
                log.error("Unable to create path: %s: %s", self.path, msg)
                return version
        
        if self.updater == "bukkitdev":
            uver, urlh = self.__bukkitdev_info()
        elif self.updater == "jenkins":
            uver, urlh = self.__jenkins_info()
        else:
            log.error("%s: invalud updater: %s" % (
                self.package, self.updater
            ))
            
            return version
        
        if not urlh:
            return version
        
        out = os.path.join(self.path, "%s.%s" % (
            self.package, self.type
        ))
        
        if uver and uver == version and not force:
            log.info("%s: already up to date" % (self.package))
            return version
        
        if not download(urlh, out):
            return version
        
        log.info("%s: updated from %s to %s" % (self.package, version, uver))
        
        if self.type != "zip":
            return uver
        
        if len(self.extract) < 1:
            return uver
        
        zf  = ZipFile(out, "r")
        cwd = os.getcwd()
        
        os.chdir(self.path)
        
        for path in self.extract:
            zf.extract(path)
        
        os.chdir(cwd)
        zf.close()
        os.remove(out)
        
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
            log.warning("Unable to get version: %s: `%s'",
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
            
            match = re.search("\"(\S+\$\S+)/\"", data)
            
            if not match:
                continue
            
            urlh = url_join(urlh, match.group(1))
            data = url_get(urlh)
            
            if not data:
                continue
            
            match = re.search("\"(artifact/\S+\.%s)\"" % (self.type), data)
            urlr  = url_join(urlh, match.group(1))
            
            return (version, urlr)
        
        return (None, None)
