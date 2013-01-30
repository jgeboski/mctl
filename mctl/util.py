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

import logging
import os
import re
import shlex
import sys
import urllib2
import urlparse

from bz2        import BZ2File
from math       import floor
from subprocess import Popen, PIPE

TIMEOUT_HTTP = 5
log          = logging.getLogger("mctl")

def execute_command(command, quiet = True):
    args = shlex.split(str(command))

    if quiet:
        p = Popen(args, 0, None, PIPE, PIPE, PIPE)
    else:
        p = Popen(args)

    p.wait()
    return p.stdout.read() if quiet else None

def screen_exists(name):
    ret   = execute_command("screen -ls")
    match = re.search("^.*\d+\.%s.*$" % (name), ret, re.MULTILINE)

    if match:
        return True

    return False

def screen_new(name, command):
    execute_command("screen -S %s -dm %s" % (name, command))

def screen_join(name):
    execute_command("screen -S %s -x" % (name), False)

def screen_command_send(name, command):
    execute_command("screen -S %s -p 0 -X stuff '%s\n'" % (name, command))

def mkdir(path):
    if os.path.isdir(path):
        return True

    try:
        os.makedirs(path)
    except Exception, msg:
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
    except Exception, msg:
        log.error("Failed to open: %s: %s", path, msg)
        fp = None

    return fp

def unlink(path):
    try:
        os.remove(path)
    except Exception, msg:
        log.error("Failed to remove: %s: %s", archive, msg)
        return False

    return True

def compress_file_bz2(path, apath):
        fp = fopen(path, "r")

        if not fp:
            return False

        try:
            bzf = BZ2File(apath, "w")
        except Exception, msg:
            log.error("Failed to open: %s: %s", apath, msg)
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

        log.info("Compressed: %s", path)
        log.info("    Output: %s", apath)
        return True

def download(url, path):
    if not url or not path:
        return False

    try:
        ul = urllib2.urlopen(url, None, TIMEOUT_HTTP)
    except Exception, msg:
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
        ul = urllib2.urlopen(rq,  None, TIMEOUT_HTTP)
    except Exception, msg:
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
