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

import asyncio
import click
import logging
import os
import time
from typing import IO, List, Optional

from mctl.config import Config, load_config
from mctl.package import (
    package_build,
    package_revisions,
    package_upgrade,
    sort_revisions_n2o,
)
from mctl.server import server_execute, server_start, server_stop

LOG = logging.getLogger(__name__)


@click.group(help="Minecraft server controller")
@click.option(
    "--config-file",
    "-c",
    help="Configuration file to use",
    envvar="FILE",
    type=click.File(),
    default=os.path.expanduser(os.path.join("~", ".mctl.yml")),
)
@click.option(
    "--debug", "-d", help="Show debugging messages", is_flag=True,
)
@click.pass_context
def cli(ctx: click.Context, config_file: IO[str], debug: bool) -> None:
    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )
    ctx.obj = load_config(config_file)


@cli.command(help="Build one or more packages")
@click.option(
    "--all-packages", "-a", help="Act on all packages", is_flag=True,
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
    help="Name(s) of the package to act on",
    envvar="PACKAGE",
    multiple=True,
)
@click.pass_obj
def build(
    config: Config, all_packages: bool, force: bool, package_name: List[str]
) -> None:
    if all_packages:
        packages = list(config.packages.values())
    elif package_name:
        packages = [config.get_package(name) for name in package_name]
    else:
        raise click.UsageError("--all-packages or --package-name required")

    # Rather than re-nicing all of the subprocesses for building, just
    # re-nice everything at a top-level (including mctl).
    if hasattr(os, "nice"):
        new_nice = os.nice(config.build_niceness)  # type: ignore
        LOG.debug("Set niceness to %s for building", new_nice)
    else:
        LOG.debug("Re-nicing not supported by this OS")

    for package in packages:
        asyncio.run(package_build(config, package, force))


@cli.command(help="Execute an arbitrary server command")
@click.argument("command", nargs=-1, envvar="COMMAND", required=True)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
)
@click.pass_obj
def execute(config: Config, command: List[str], server_name: str) -> None:
    server = config.get_server(server_name)
    asyncio.run(server_execute(server, " ".join(command)))


@cli.command(help="List all packages")
@click.pass_obj
def packages(config: Config) -> None:
    for package in config.packages.values():
        click.echo(f"{package.name}:")
        if package.repo:
            click.echo(f"  Repo URL: {package.repo.url}")
            click.echo(f"  Repo Type: {package.repo.type}")
            click.echo(f"  Repo Branch: {package.repo.branch}")

        if package.fetch_urls:
            click.echo(f"  Fetch URLs:")
            for url in package.fetch_urls:
                click.echo(f"    - {url}")

        click.echo(f"  Build Commands:")
        for command in package.build_commands:
            click.echo(f"    - {command}")

        click.echo(f"  Artifacts:")
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
    "--message", "-m", help="Restart message show to players", envvar="MESSAGE",
)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
)
@click.pass_obj
def restart(config: Config, message: Optional[str], server_name: str) -> None:
    server = config.get_server(server_name)
    asyncio.run(server_stop(server, message))
    asyncio.run(server_start(server))


@cli.command(help="List all servers")
@click.pass_obj
def servers(config: Config) -> None:
    for server in config.servers.values():
        click.echo(f"{server.name}:")
        click.echo(f"  Path: {server.path}")
        click.echo(f"  Command: {server.command}")
        click.echo(f"  Stop Timeout: {server.stop_timeout}")
        click.echo(f"  Packages:")

        for package in server.packages:
            click.echo(f"    - {package}")

        click.echo("")


@cli.command(help="Start a server")
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
)
@click.pass_obj
def start(config: Config, server_name: str) -> None:
    server = config.get_server(server_name)
    asyncio.run(server_start(server))


@cli.command(help="Stop a server")
@click.option(
    "--message", "-m", help="Shutdown message show to players", envvar="MESSAGE",
)
@click.option(
    "--server-name",
    "-s",
    help="Name of the server to act on",
    envvar="SERVER",
    required=True,
)
@click.pass_obj
def stop(config: Config, message: Optional[str], server_name: str) -> None:
    server = config.get_server(server_name)
    asyncio.run(server_stop(server, message))


@cli.command(help="Upgrade one or more packages")
@click.option(
    "--all-packages", "-a", help="Act on all packages", is_flag=True,
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
    help="Name(s) of the package to act on",
    envvar="PACKAGE",
    multiple=True,
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
)
@click.pass_obj
def upgrade(
    config: Config,
    all_packages: bool,
    force: bool,
    package_name: List[str],
    revision: Optional[str],
    server_name: str,
) -> None:
    if (all_packages or len(package_name) > 1) and revision:
        raise click.UsageError("Only a single package can be used with --revision")

    if all_packages:
        packages = list(config.packages.values())
    elif package_name:
        packages = [config.get_package(name) for name in package_name]
    else:
        raise click.UsageError("--all-packages or --package-name required")

    server = config.get_server(server_name)
    for package in packages:
        asyncio.run(package_upgrade(config, server, package, revision, force))
