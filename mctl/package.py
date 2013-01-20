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
    def __init__(self, name, package, swd, dryrun):
        self.package = name
        self.path    = package['path']
        self.type    = package['type']
        self.url     = package['url']
        self.updater = package['updater']
        self.extract = package['extract']
        self.dryrun  = dryrun

        if self.path:
            self.path = os.path.join(swd, self.path)
        else:
            self.path = swd

    def upgrade(self, version, force = False):
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

        out = os.path.join(self.path, "%s.%s" % (self.package, self.type))

        if uver and uver == version and not force:
            log.info("%s: package already up-to-date", self.package)
            return version

        if not self.dryrun and not download(urlh, out):
            return version

        log.info("%s: package upgraded: %s -> %s", self.package, version, uver)

        if self.dryrun or (self.type != "zip"):
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
            log.warning("Failed to extract version: reported version `%s'",
                        version)

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
            ".*dl.bukkit.org/downloads/(\w+)(?:/(?:list)/(\w+))?/?", self.url)

        if not match or not match.group(1):
            log.error("Failed to parse URL: %s: invalid bukkitdl URL", self.url)
            return (None, None)

        urlh = "http://dl.bukkit.org/api/1.0/downloads/" \
               "projects/%s/artifacts/" % (match.group(1))

        if match.lastindex == 2:
            urlh += "%s/" % (match.group(2))

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

        try:
            dom = minidom.parseString(data)
        except Exception, msg:
            log.error("Failed to parse XML: %s: %s", urlh, msg)
            return (None, None)

        for entry in dom.getElementsByTagName("entry"):
            title = _xml_child_get(entry, "title")
            title = title.firstChild.nodeValue
            match = re.match(".* #([A-Za-z0-9_-]+) \((.*)\)", title)

            if not match:
                continue

            version = match.group(1)
            state   = match.group(2)
            match   = "^(?:stable|back to normal|" \
                      "(?:\d+) test?s are still failing)$"

            if not re.match(match, state, re.I):
                continue

            urlh = _xml_child_get(entry, "link")
            urlh = urlh.getAttribute("href")
            data = url_get(urlh)

            if not data:
                continue

            fr    = "\S*%s\S*-SNAPSHOT.%s" % (self.package, self.type)
            match = re.search("\"(artifact/%s)\"" % (fr), data, re.I)

            if not match:
                fr    = "\S+.%s" % (self.type)
                match = re.search("\"(artifact/%s)\"" % (fr), data, re.I)

            if match:
                urlr = url_join(urlh, match.group(1))
                return (version, urlr)

            match = re.search("\"(\S+\$%s)/\"" % (self.package), data, re.I)

            if not match:
                continue

            urlh = url_join(urlh, match.group(1))
            data = url_get(urlh)

            if not data:
                continue

            match = re.search("\"(artifact/%s)\"" % (fr), data, re.I)

            if not match:
                log.warning("Failed to extract download URL: (version: %s) "
                            "reverting to previous version", version)
                continue

            urlr  = url_join(urlh, match.group(1))

            return (version, urlr)

        return (None, None)
