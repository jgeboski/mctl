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
import io
import logging
import os
from typing import IO


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
def cli(config_file: IO[str], debug: bool) -> None:
    logging.basicConfig(
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )


@cli.command(help="Build one or more packages")
def build() -> None:
    pass


@cli.command(help="Execute an arbitrary server command")
def execute() -> None:
    pass


@cli.command(help="List all packages")
def packages() -> None:
    pass


@cli.command(help="Restart a server")
def restart() -> None:
    pass


@cli.command(help="List all servers")
def servers() -> None:
    pass


@cli.command(help="Start a server")
def start() -> None:
    pass


@cli.command(help="Stop a server")
def stop() -> None:
    pass


@cli.command(help="Upgrade one or more packages")
def upgrade() -> None:
    pass
