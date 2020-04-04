# MCTL

MCTL is a python tool for automating and reducing the operational cost
of running Minecraft servers. MCTL provides a number of features:

* Management (starting and stopping) of one or more servers.
* Plugin management (building, updating, and snapshotting).
* Fake server when the main server is offline, showing a status message.
* All of this wrapped up in an easy to use CLI.

# Installing

## Dependencies

* Python >= 3.7
* [Click](https://click.palletsprojects.com)
* [aiofiles](https://github.com/Tinche/aiofiles)
* [aiohttp](https://docs.aiohttp.org)
* [Git](https://git-scm.com)
* [GNU Screen](https://www.gnu.org/software/screen)
* [PyYAML](https://pyyaml.org)

## Fedora

```
$ sudo dnf copr enable jgeboski/mctl
$ sudo dnf install mctl
$ mkdir -p ~/.mctl
$ cp /usr/share/doc/mctl/config.yml ~/.mctl
```

## Manually (Linux)

```
$ mkdir -p ~/.mctl ~/bin
$ git clone https://github.com/jgeboski/mctl.git ~/.mctl/source
$ ln -sf ~/.mctl/source/mctl.py ~/bin/mctl
$ chmod +x ~/bin/mctl
$ cp ~/.mctl/source/config.yml ~/.mctl
$ echo PATH=\"\$PATH:\$HOME/bin\" >> ~/.bashrc
$ . ~/.bashrc
```

# Usage

Make sure to configure MCTL in `~/.mctl/config.yml` before proceeding!

## Showing help

```
$ mctl --help
$ mctl <command> --help
```

## Listing servers and packages

```
$ mctl servers
$ mctl packages
```

## Starting a server

```
$ mctl start -s <server name>
```

## Stopping a server

```
$ mctl stop -s <server name> -m "<Reason for stopping>"
```

## Restarting a server

```
$ mctl restart -s <server name> -m "<Reason for restarting (ex: updating plugins)>"
```

## Updating packages

```
$ mctl build --all-packages
$ mctl upgrade -s <server name> --all-packages
$ mctl restart -s <server name> -m "Updating server packages"
```

## Stopping a server, starting the fake server

```
$ mctl stop -s <server name> -m "<Reason for stopping>" -k
```

## Starting the fake server by itself

```
$ mctl start -s <server name> -m "<Reason for the server being down>" -k
```

## Stopping the fake server

```
$ mctl stop -s <server name>
```

## Debugging

```
$ mctl -d <command>
```