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

import click
import logging
import os
from typing import IO

from mctl.config import Config, load_config


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
@click.pass_obj
def build(config: Config) -> None:
    pass


@cli.command(help="Execute an arbitrary server command")
@click.pass_obj
def execute(config: Config) -> None:
    pass


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

        click.echo("")


@cli.command(help="Restart a server")
@click.pass_obj
def restart(config: Config) -> None:
    pass


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
@click.pass_obj
def start(config: Config) -> None:
    pass


@cli.command(help="Stop a server")
@click.pass_obj
def stop(config: Config) -> None:
    pass


@cli.command(help="Upgrade one or more packages")
@click.pass_obj
def upgrade(config: Config) -> None:
    pass
