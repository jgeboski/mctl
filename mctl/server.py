import logging
import os
import re
import shlex
import time

from package    import Package
from subprocess import Popen, PIPE

log = logging.getLogger("server")

def _screen_exists(name):
    ret   = _execute_command("screen -ls")
    match = re.search("^.*\d+\.%s.*$" % (name), ret, re.MULTILINE)
    
    if match:
        return True
    
    return False

def _screen_new(name, command):
    _execute_command("screen -S %s -dm %s" % (name, command))

def _screen_join(name):
    _execute_command("screen -S %s -x" % name, False)

def _screen_command_send(name, command):
    _execute_command(
        "screen -S %s -p 0 -X stuff '%s\n'" % (name, command))

def _execute_command(command, quiet = True):
    args = shlex.split(str(command))
    
    if quiet:
        p = Popen(args, 0, None, PIPE, PIPE, PIPE)
    else:
        p = Popen(args)
    
    p.wait()
    return p.stdout.read() if quiet else None

class Server:
    def __init__(self, name, server):
        self.server       = name
        self.path         = server['path']
        self.launch       = server['launch']
        self.timeout      = server['timeout']
        self.log_size     = server['log-size']
        self.log_path     = server['log-path']
        self.backup_max   = server['backup-max']
        self.backup_path  = server['backup-path']
        self.backup_paths = server['backup-paths']
        self.packages     = server['packages']
        
        self.screen_name = "mcctl-%s" % (name)
        
    def command(self, command):
        _screen_command_send(self.screen_name, command)
    
    def backup(self, server):
        print "[TODO] Backup..."
    
    def update(self, config, force = False):
        for package in self.packages:
            cpkg = config.package_get(package)
            pkg  = Package(package, cpkg, self.path)
            
            version = pkg.update(force)
            
            if not version:
                continue
            
            cpkg['version'] = version
            config.package_set(package, cpkg)
        
        config.save()
        return config
    
    def start(self):
        cwd = os.getcwd()
        
        if _screen_exists(self.screen_name):
            log.error("server already running")
            return
        
        os.chdir(self.path)
        _screen_new(self.screen_name, self.launch)
        os.chdir(cwd)
        
    def stop(self, message = None):
        if not _screen_exists(self.screen_name):
            log.error("server it not running")
            return
        
        if message:
            self.command('say %s' % (message))
        
        s = self.timeout
        
        if s >= 10:
            while s > 0:
                say = "Server stopping in %s second(s)" % (s)
                
                self.command("say %s" % (say))
                log.info(say)
                
                s -= 10
                time.sleep(10)
        
        self.command("save-all")
        self.command("stop")
        
        _screen_join(self.screen_name)
    
    def restart(self, message = None):
        self.stop(message)
        self.start()
