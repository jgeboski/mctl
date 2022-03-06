#!/usr/bin/env python3

# Copyright 2012-2020 James Geboski <jgeboski@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

import sys

import click
import logging
import os
import time
from typing import Any, Callable, List, Optional

from mctl.config import Config, load_config, Package, Server
from mctl.exception import MctlError
from mctl.fake_server import (
    DEFAULT_MESSAGE,
    DEFAULT_MOTD,
    DEFAULT_PORT,
    run_fake_server,
)
from mctl.package import (
    package_build,
    package_revisions,
    package_upgrade,
    sort_revisions_n2o,
)
from mctl.server import server_execute, server_start, server_start_fake, server_stop
from mctl.util import await_sync

DEFAULT_CONFIG_FILE = os.path.expanduser(os.path.join("~", ".mctl/config.yml"))
LOG = logging.getLogger(__name__)


class MctlCommand(click.Command):
    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
            return super().invoke(*args, **kwargs)

        try:
            return super().invoke(*args, **kwargs)
        except MctlError as ex:
            raise click.ClickException(str(ex))


class MctlRootGroup(click.Group):
    def command(self, *args: Any, **kwargs: Any) -> Callable:
        kwargs["cls"] = MctlCommand
        return super().command(*args, **kwargs)


def get_packages(
    config: Config,
    all_packages: bool,
    all_except: Optional[List[str]],
    package_names: Optional[List[str]],
    server: Optional[Server] = None,
) -> List[Package]:
    server_pkg_names = server.packages if server else list(config.packages)
    if all_except:
        for name in all_except:
            config.get_package(name)

        selected_names = [name for name in server_pkg_names if name not in all_except]
    elif all_packages:
        selected_names = server_pkg_names
    elif package_names:
        selected_names = package_names
    else:
        raise click.UsageError(
            "--all-packages, --all-except, or --package-name required"
        )

    packages = [config.get_package(name) for name in selected_names]
    if len(packages) == 0:
        raise click.ClickException("No packages selected with the specified options")

    return packages


@await_sync
async def shell_complete_package_name(
    context: click.Context, param: click.Parameter, incomplete: str
) -> List[str]:
    try:
        config = await load_config(DEFAULT_CONFIG_FILE)
    except Exception:
        return []

    return [package for package in config.packages if package.startswith(incomplete)]


@await_sync
async def shell_complete_server_name(
    context: click.Context, param: click.Parameter, incomplete: str
) -> List[str]:
    try:
        config = await load_config(DEFAULT_CONFIG_FILE)
    except Exception:
        return []

    return [server for server in config.servers if server.startswith(incomplete)]


@click.group(help="Minecraft server controller", cls=MctlRootGroup)
@click.option(
    "--config-file",
    "-c",
    help="Configuration file to use",
    envvar="FILE",
    default=DEFAULT_CONFIG_FILE,
)
@click.option(
    "--debug",
    "-d",
    help="Show debugging messages",
    is_flag=True,
)
@click.pass_context
@await_sync
async def cli(ctx: click.Context, config_file: str, debug: bool) -> None:
    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )
    ctx.obj = await load_config(config_file)


@cli.command(help="Build one or more packages")
@click.option(
    "--all-packages",
    "-a",
    help="Act on all packages",
    is_flag=True,
)
@click.option(
    "--all-except",
    "-e",
    help="Act on all packages except these (can be specified multiple times)",
    envvar="PACKAGE",
    multiple=True,
    shell_complete=shell_complete_package_name,
)
@click.option(
    "--force",
    "-f",
    help="Force packages to build even if the revision already exists",
    is_flag=True,
)
@click.option(
    "--package-name",
    "-p",
    help="Name(s) of the package to act on (can be specified multiple times)",
    envvar="PACKAGE",
    multiple=True,
    shell_complete=shell_complete_package_name,
)
@click.pass_obj
@await_sync
async def build(
    config: Config,
    all_packages: bool,
    all_except: Optional[List[str]],
    force: bool,
    package_name: Optional[List[str]],
) -> None:
    packages = get_packages(config, all_packages, all_except, package_name)
    # Rather than re-nicing all of the subprocesses for building, just
    # re-nice everything at a top-level (including mctl).
    if hasattr(os, "nice"):
        new_nice = os.nice(config.build_niceness)  # type: ignore
        LOG.debug("Set niceness to %s for building", new_nice)
    else:
        LOG.debug("Re-nicing not supported by this OS")

    for package in packages:
        await package_build(config, package, force)


@cli.command(help="Execute an arbitrary server command")
@click.argument("command", nargs=-1, envvar="COMMAND", required=True)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
    shell_complete=shell_complete_server_name,
)
@click.pass_obj
@await_sync
async def execute(config: Config, command: List[str], server_name: str) -> None:
    server = config.get_server(server_name)
    await server_execute(server, " ".join(command))


@cli.command("fake-server", help="Run the fake server in the foreground")
@click.option(
    "--listen-address",
    "-l",
    help="IPv4/IPv6 address to listen on",
    envvar="ADDRESS",
)
@click.option("--icon-file", "-i", help="PNG icon to use", envvar="FILE")
@click.option(
    "--message",
    "-m",
    help="Message to disconnect players with",
    envvar="MESSAGE",
    default=DEFAULT_MESSAGE,
)
@click.option(
    "--motd",
    "-t",
    help="Message of the day to display",
    envvar="MESSAGE",
    default=DEFAULT_MOTD,
)
@click.option(
    "--port",
    "-p",
    help="Port to listen on",
    envvar="PORT",
    default=DEFAULT_PORT,
)
@click.pass_obj
@await_sync
async def fake_server(
    config: Config,
    listen_address: Optional[str],
    icon_file: Optional[str],
    message: str,
    motd: str,
    port: int,
) -> None:
    await run_fake_server(listen_address, port, message, motd, icon_file)


@cli.command(help="List all packages")
@click.pass_obj
def packages(config: Config) -> None:
    for package in config.packages.values():
        click.echo(f"{package.name}:")
        if package.repositories:
            click.secho("  Repositories:")
            for repo in package.repositories.values():
                click.echo(f"    URL: {repo.url}")
                click.echo(f"    Type: {repo.type}")
                click.echo(f"    Committish: {repo.committish}")

        if package.fetch_urls:
            click.echo("  Fetch URLs:")
            for path, url in package.fetch_urls.items():
                click.echo(f"    - {path}: {url}")

        click.echo("  Build Commands:")
        for command in package.build_commands:
            click.echo(f"    - {command}")

        click.echo("  Artifacts:")
        for name, regex in package.artifacts.items():
            click.echo(f"    - {regex} -> {name}")

        revs = package_revisions(config, package)
        if revs:
            click.secho("  Built Revisions:")
            for rev, ts in sort_revisions_n2o(revs):
                click.secho(f"    - {rev} ({time.ctime(ts)})")

        click.echo("")


@cli.command(help="Restart a server")
@click.option(
    "--message",
    "-m",
    help="Restart message show to players",
    envvar="MESSAGE",
)
@click.option(
    "--now",
    "-n",
    help="Restart the server now without waiting the server-timeout",
    is_flag=True,
)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
    shell_complete=shell_complete_server_name,
)
@click.pass_obj
@await_sync
async def restart(
    config: Config, message: Optional[str], now: bool, server_name: str
) -> None:
    server = config.get_server(server_name)
    await server_stop(server, message, not now)
    await server_start(server)


@cli.command(help="List all servers")
@click.pass_obj
def servers(config: Config) -> None:
    for server in config.servers.values():
        click.echo(f"{server.name}:")
        click.echo(f"  Path: {server.path}")
        click.echo(f"  Command: {server.command}")
        click.echo(f"  Stop Timeout: {server.stop_timeout}")
        click.echo("  Packages:")

        for package in server.packages:
            click.echo(f"    - {package}")

        click.echo("")


@cli.command(help="Start a server")
@click.option(
    "--fake",
    "-k",
    help="Start the fake server instead",
    is_flag=True,
)
@click.option(
    "--fake-message",
    "-m",
    help="Use this message for the fake server",
    envvar="MESSAGE",
)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
    shell_complete=shell_complete_server_name,
)
@click.pass_obj
@await_sync
async def start(
    config: Config, fake: bool, fake_message: Optional[str], server_name: str
) -> None:
    server = config.get_server(server_name)
    if fake:
        await server_start_fake(server, fake_message)
    else:
        await server_start(server)


@cli.command(help="Stop a server")
@click.option(
    "--message",
    "-m",
    help="Shutdown message show to players",
    envvar="MESSAGE",
)
@click.option(
    "--now",
    "-n",
    help="Stop the server now without waiting the server-timeout",
    is_flag=True,
)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
    shell_complete=shell_complete_server_name,
)
@click.option(
    "--start-fake",
    "-k",
    help="Start the fake server when the server is stopped",
    is_flag=True,
)
@click.pass_obj
@await_sync
async def stop(
    config: Config,
    message: Optional[str],
    now: bool,
    server_name: str,
    start_fake: bool,
) -> None:
    server = config.get_server(server_name)
    await server_stop(server, message, not now)
    if start_fake:
        await server_start_fake(server, message)


@cli.command(help="Upgrade one or more packages")
@click.option(
    "--all-packages",
    "-a",
    help="Act on all packages",
    is_flag=True,
)
@click.option(
    "--all-except",
    "-e",
    help="Act on all packages except these (can be specified multiple times)",
    envvar="PACKAGE",
    multiple=True,
    shell_complete=shell_complete_package_name,
)
@click.option(
    "--force",
    "-f",
    help="Force packages to upgrade even if they are up-to-date",
    is_flag=True,
)
@click.option(
    "--package-name",
    "-p",
    help="Name(s) of the package to act on (can be specified multiple times)",
    envvar="PACKAGE",
    multiple=True,
    shell_complete=shell_complete_package_name,
)
@click.option(
    "--revision",
    "-n",
    help="Revision (or version) of the package to upgrade or downgrade to",
    envvar="REV",
)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
    shell_complete=shell_complete_server_name,
)
@click.pass_obj
@await_sync
async def upgrade(
    config: Config,
    all_packages: bool,
    all_except: Optional[List[str]],
    force: bool,
    package_name: Optional[List[str]],
    revision: Optional[str],
    server_name: str,
) -> None:
    server = config.get_server(server_name)
    packages = get_packages(config, all_packages, all_except, package_name, server)
    for package in packages:
        await package_upgrade(config, server, package, revision, force)
