import logging
import os
import re
import util

from util    import download, url_get, url_join
from xml.dom import minidom
from zipfile import ZipFile

log = logging.getLogger("package")

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
        self.version = package['version']
        self.path    = package['path']
        self.type    = package['type']
        self.url     = package['url']
        self.updater = package['updater']
        self.extract = package['extract']
        
        if self.path:
            self.path = os.path.join(swd, self.path)
        else:
            self.path = swd
    
    def update(self, force = False):
        if not os.path.isdir(self.path):
            try:
                os.makedirs(self.path)
            except os.error, msg:
                log.error("Unable to create path: %s: %s", self.path, msg)
                return self.version
        
        if self.updater == "bukkitdev":
            version, urlh = self.__bukkitdev_info()
        elif self.updater == "jenkins":
            version, urlh = self.__jenkins_info()
        else:
            log.error("%s: invalud updater: %s" % (
                self.package, self.updater
            ))
            
            return self.version
        
        if not version or not urlh:
            return self.version
        
        out = os.path.join(self.path, "%s.%s" % (
            self.package, self.type
        ))
        
        if version == self.version and not force:
            log.info("%s: already up to date" % (self.package))
            return self.version
        
        if not download(urlh, out):
            return self.version
        
        log.info("%s: updated from %s to %s" % (
            self.package, self.version, version
        ))
        
        if self.type != "zip":
            return version
        
        if len(self.extract) < 1:
            return version
        
        zf  = ZipFile(out, "r")
        cwd = os.getcwd()
        
        os.chdir(self.path)
        
        for path in self.extract:
            zf.extract(path)
        
        os.chdir(cwd)
        zf.close()
        os.remove(out)
        
        return version
    
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
        
        match   = re.search("((?:\d+\.)(?:\w+\.)?(?:\w+\.)?(?:\w+))", version)
        version = match.group(1)
        
        urlh = _xml_child_get(item, "link")
        data = url_get(urlh.firstChild.nodeValue)
        
        if not data:
            return (None, None)
        
        match = re.search(
            "<a href=\"(\S*\.%s)\">Download</a>" % (self.type), data)
        
        if not match:
            return (None, None)
        
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
